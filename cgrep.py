#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import getopt
import signal

import re
import fnmatch

VERSION = "3.001 2017-10-12"

HELP = """
  Advanced grep tool that can:

  find a file recursively:
    cgrep -o outfile -g[is] -x exclude filename_glob dir1 dir2

  find pattern in file
    cgrep -o outfile -e -x exclude filename_glob dir

  scoped find (ctags support)
    cgrep -t filename.tag scope:pattern
    (where scope: p - prototype, f - function, c - class, s - struct, m - member, t - type)

  Tips:
    Build tag file:
      ctags -R --c++-types=+px --extra=+q --excmd=pattern --exclude=Makefile --exclude=.tags -f .tags
    Overwrite default skip: ~/.cgrep_skip.txt or ~/.config/cgrep/skip.txt
      skip_dir = [".hg", ".git", ".svn", "CVS", "RCS", "SCCS"]
      skip_ext = [".bin", ".o", ".obj", ".class", ".so"]
"""


""" Parameters """
_skip_dir = [".hg", ".git", ".svn", "CVS", "RCS", "SCCS"]
_skip_ext = [".bin", ".o", ".obj", ".class", ".so", ".dynlib", ".dll", ".zip", ".jar", ".gz", ".gch", ".pch", ".pdb", ".swp", ".jpg", ".ttf"]
_skip_files = [".cgrep_skip.txt", "~/.cgrep_skip.txt", "~/.config/cgrep/skip.txt"]
_skip_fullfilename = []

_max_line_part = 40

_arg_re_flags = 0
_arg_dirsonly = False
_arg_word = False
_arg_warn_skip = True
_arg_no_skip = False
_arg_context = False
_arg_outfile = None

""" global varables """

_search_kind = "grep"

_extra_skip_dir = []
_extra_skip_ext = []
_extra_skip_re = []
_out_fd = None
_html_output = False

known_scopes_ = ["p","f","c","s","m","t"]

""" Fancy printing """
class Color(object):
  COLOR = "\033[%dm%s\033[0m"
  ANSI_COLORS = {"default" : 0, "black" : 30, "red" : 31, "green" : 32,
                 "yellow" : 33, "blue" : 34, "magenta" : 35, "cyan" : 36,
                 "white" : 37}
  
  HTML_COLORS = {"default" : "", "black" : "#000000", "red" : "#aa0000", "green" : "#00aa00",
                 "yellow" : "#aaaa00", "blue" : "#0000aa", "magenta" : "#aa00aa", "cyan" : "#00aaaa",
                 "white" : "#ffffff"}

  def __init__(self):
    self.enabled = True

  def disable(self):
    self.enabled = False

  def toggle(self):
    self.enabled = not self.enabled

  def cl(self, color=None, msg=""):
    if not self.enabled:
      return msg

    if color is None or color == "/":
      return "\033[0m"

    if msg != "":
      return "\033[%dm%s\033[0m" % (Color.ANSI_COLORS[color], msg)

    return "\033[%dm" % Color.ANSI_COLORS[color]
  
  def html(self, color, msg):
    if color is None or color == "/":
      return "</FONT>"

    if msg != "":
      return "<FONT color='%s'>%s</FONT>" % (Color.HTML_COLORS[color], msg.replace(" ", "&nbsp;"))

    return "<FONT color='%s'>" % Color.HTML_COLORS[color]
 
  def eol(self, need_eol):
    if need_eol:
      return "\n"
    return ""

  def html_eol(self, need_eol):
    if need_eol:
      return "<br />\n"
    return ""
 
  def prn(self, color, msg, need_eol = True):
    if _out_fd != None:
      if _html_output:
        _out_fd.write(self.html(color, msg) + self.html_eol(need_eol)) 
      else:
        _out_fd.write(msg + self.eol(need_eol))
    sys.stdout.write(self.cl(color, msg) + self.eol(need_eol))
      
  def ref(self, color, msg, filename):
    if _out_fd != None:
      if _html_output:
        _out_fd.write("""<A href="%s">%s</A><BR />\n""" % (filename, self.html(color, msg)))
      else:
        _out_fd.write(msg + "\n")
    print (self.cl(color, msg))

_color = Color()

def should_skip_dir(dirname):
  """ Check additional skip conditions """
  if _arg_no_skip:
    return (False, None)

  if dirname in _skip_dir:
    """ Hardcoded skip, we need not to print extra information about """
    return (True, None)

  for dn in _extra_skip_dir:
    if dirname.find(dn) != -1:
      """ Soft skip, warn, because it can cause information miss """
      return (True, dn)

  for (rere, restr) in _extra_skip_re:
    if rere.match(dirname):
      return (True, restr)
  return (False, None)

def should_skip_file(filename):
  """ Check additional skip conditions """
  if _arg_no_skip:
    return False

  if len(_skip_fullfilename) > 0:
    fullfilename = os.path.join(os.getcwd(), filename)
    if fullfilename in _skip_fullfilename:
      return True
 
  (fname, ext) = os.path.splitext(filename) #pylint: disable=unused-variable
  if ext in _skip_ext:
    return True

  if ext in _extra_skip_ext:
    return True
  return False

def grep_file(filename, pattern):
  line_count = 0
  good_lines = []
  kp = (0, "", "", "")
  with open(filename, "r") as fd:
    for ln in fd:
      line_count += 1
      m = pattern.search(ln)
      if m != None:
        a = m.string[:m.start(0)]
        b = m.string[m.start(0):m.end(0)]
        c = m.string[m.end(0):-1]
        if len(a) > _max_line_part:
          a = "..." + a[len(a)-_max_line_part:]
        if len(c) > _max_line_part:
          c = c[:_max_line_part] + "..."
        if _arg_context:
          good_lines.append(kp)
          good_lines.append((line_count, a, b, c))
          good_lines.append((line_count + 1, next(fd, ''), "", ""))
        else:
          good_lines.append((line_count, a, b, c))
      kp = (line_count, ln[:-1], "", "")
  return good_lines

def print_good_line(good_line):
  (n, a, b, c) = good_line
  if b != "" or c != "":
    _color.prn("default", "%4d: %s" % (n, a), False)
    _color.prn("green", b, False)
    _color.prn("default", c, True)
  else:
    _color.prn("default", "%4d: %s" % (n, a))

""" grep search """
def do_grep(filepattern, textpattern, dirname):
  for root, dirs, files in os.walk(dirname, topdown=True):
    for name in dirs:
      fn = os.path.join(root, name)
      (flag, text) = should_skip_dir(name)
      if flag:
        dirs.remove(name)
        if text != None and _arg_warn_skip:
          _color.ref("magenta", "Skipped (%s) %s " % (text, fn), os.path.abspath(fn))
        continue
    for name in files:
      if filepattern.search(name):
        fn = os.path.join(root, name)
        if should_skip_file(name):
          continue
        try:
          good_lines = grep_file(fn, textpattern)
          if len(good_lines) > 0:
            _color.ref("yellow", fn, os.path.abspath(fn))
            for good_line in good_lines:
              print_good_line(good_line)
        except Exception as e:
          print _color.cl("magenta", fn), e

""" filename search """
def do_glob(pattern, dirname):
  for root, dirs, files in os.walk(dirname, topdown=True):
    for name in dirs:
      fn = os.path.join(root, name)
      (flag, text) = should_skip_dir(name)
      if flag:
        dirs.remove(name)
        if text != None and _arg_warn_skip:
          _color.prn("magenta", "Skipped [%s] %s" % (text, fn))
        continue
      if pattern.search(name):
        _color.prn("yellow", fn)
    if _arg_dirsonly:
      continue

    for name in files:
      if pattern.search(name):
        fn = os.path.join(root, name)
        if not should_skip_file(name):
          _color.prn("default", fn)

def parse_tag_line(p_ln, p_scope, p_ident_re):
  if p_ln.startswith("!"):
    """ Skip comments """
    return (None, None, None)

  try:
    (tagname, srcfile, tagpattern, scope) = p_ln.split("\t", 3)
  except ValueError as ex:
    print "CTAGS line format error: '%s'" % ln
    return (None, None, None)

  scope = scope[0]
  if scope != p_scope:
    """ Skip wrong scope """
    return (None, None, None)

  if p_ident_re.match(tagname) == None:
    """ Skip wrong ident """
    return (None, None, None)

  tagpattern = tagpattern[1:-3] if tagpattern.endswith(';"') else tagpattern[1:-1]
  tagpattern = tagpattern.replace("(", "\\(")
  tagpattern = tagpattern.replace(")", "\\)")

  try:
    tag_re = re.compile(tagpattern[1:-3])
  except Exception as ex:
    print "CTAGS re format error: '%s'" % tagpattern
    return (None, None, None)

  return (tagname, srcfile, tag_re)

def do_ctags(tagfile, scope, ident):
  ident_re = re.compile(ident, _arg_re_flags)
  found_lines = dict()

  with open(args[0], "r") as tagf:
    for ln in tagf:
      (tagname, srcfile, tag_re) = parse_tag_line(ln, scope, ident_re)
      if tagname != None:
        good_lines = grep_file(srcfile, tag_re)
        for (n, a, b, c) in good_lines:
          found_lines["%s:%04d" % (srcfile, int(n))] = (n, a, b, c)

  kept_fn = None
  for key in sorted(found_lines.keys()):
    fn = key.split(":")[0]
    if fn != kept_fn:
      _color.ref("yellow", fn, os.path.abspath(fn))
      kept_fn = fn
    print_good_line(found_lines[key])

def skip_from_file(filename):
  (skip_dir, skip_ext) = ([], [])
  with open(filename,'r') as inf:
    data = inf.read()

  m = re.search("skip_dir[ \t]*=[ \t]*(\[.*\])", data)
  if m is not None:
    skip_dir = eval(m.group(1))

  m = re.search("skip_ext[ \t]*=[ \t]*(\[.*\])", data)
  if m is not None:
    skip_ext = eval(m.group(1))
  return (skip_dir, skip_ext)

""" Support function """
def fatal(msg, e=None):
  s = " (%s)" % str(e) if e != None else ""
  print _color.cl("red", msg + s)
  sys.exit(-1)

def usage():
  print HELP
  sys.exit(7)

def signal_handler(signal, frame): #pylint: disable=unused-argument
  sys.stdout.write("\nInterrupted. Exiting ...\n")
  sys.exit(-1)

if __name__ == '__main__':
  """ set ctrl-C handler and reopen stdout unbuffered """
  signal.signal(signal.SIGINT, signal_handler)
  sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

  if os.path.basename(sys.argv[0]) == "cgrep":
    _search_kind = 'grep'
  elif os.path.basename(sys.argv[0]) == "cfind":
    _search_kind = 'glob'

  try:
    opts, args = getopt.getopt(sys.argv[1:],
                               "hcegdisSux:to:",
                               ["help", "color", "grep", "glob", "dirsonly", "ignorecase", "warnskip", "noskip", "context", "exclude", "tags", "output"])
  except getopt.GetoptError as err:
    print str(err)
    usage()

  extra_skip = list()
  if os.name == 'nt':
    """ Disable color output on windows by default """
    _color.disable()

  for o, a in opts:
    if o in ("-c", "--color"):
      """Use ansy color on printing"""
      _color.toggle()
    elif o in ("-e", "--grep"):
      _search_kind = "grep"
    elif o in ("-g", "--glob"):
      _search_kind = "glob"
    elif o in ("-t", "--tags"):
      _search_kind = "tags"
    elif o in ("-x", "--exclude"):
      """ List of additional extensions and/or directories to filter out
          test:build:/.*class/:.back
      """
      extra_skip += a.split(":")
    elif o in ("-d", "--dirsonly"): 
      _arg_dirsonly = True
    elif o in ("-i", "--ignorecase"):
      _arg_re_flags |= re.IGNORECASE
    elif o in ("-s", "--warnskip"):
      _arg_warn_skip = False
    elif o in ("-S", "--noskip"):
      _arg_no_skip = True
    elif o in ("-u", "--context"):
      _arg_context = True
    elif o in ("-o", "--output"):
      """ Redirect all output to a file """
      _arg_outfile = a
    elif o in ("-h", "--help"):
      usage()
    else:
      assert False, "unhandled option"

  if len(args) == 0:
    usage()

  """ Read skip from file """
  (fskip_dir, fskip_ext) = ([], [])
  for fn in _skip_files:
    fns = os.path.expanduser(fn)
    if os.path.exists(fns):
      (skip_dir, skip_ext) = skip_from_file(fns)
      fskip_dir += skip_dir
      fskip_ext += skip_ext

  """ Override defaults if skiplist we read from files is not empty """
  if len(fskip_dir) > 0:
    _skip_dir = list(set(fskip_dir))
  if len(fskip_ext) > 0:
    _skip_ext = list(set(fskip_ext))

  """ Pre-process extra skip """
  for n in extra_skip:
    if n[0] == '.':
      _extra_skip_ext.append(n)
    elif n[0] == '/':
      assert n[-1] == '/', "bad regex"
      _extra_skip_re.append((re.compile(n[1:-1]), n[1:-1]))
    else:
      _extra_skip_dir.append(n)

  filepat = None
  textpat = None
  
  if _arg_outfile != None:
    """ Redirect all output to file. Rely on OS to close it """
    _arg_outfile = os.path.abspath(_arg_outfile)
    _skip_fullfilename.append(_arg_outfile)
    
    _out_fd = file(_arg_outfile, "w")
    
    """ Enable color output in html format if outfile have html ext """
    lw_outfile = _arg_outfile.lower()
    if lw_outfile.endswith(".html") or lw_outfile.endswith(".htm"):
      _html_output = True

  if _search_kind == "grep":
    """ args should be textpattern filepattern dir1 ... dirN"""
    if len(args) == 1:
      """ only textpattern present """
      args.append("*")
    if len(args) == 2 and not os.path.isdir(args[1]):
      """ dirlist is missed """
      args.append(".")
    if len(args) >= 2 and os.path.isdir(args[1]):
      """ filepattern missed """
      args.insert(2, "*")

    textpat = re.compile(args[0], _arg_re_flags)

    """ file pattern is glob and case sensitive """
    p = fnmatch.translate(args[1])
    filepat = re.compile(p, 0)
    for d in args[2:]:
      do_grep(filepat, textpat, d)

  elif _search_kind == "glob":
    """ args should be filepattern dir1 ... dirN"""
    if len(args) == 1:
      """ dirlist is missed """
      args.append(".")

    pat = args[0]
    if pat[0] == '/' and pat[-1] == '/':
      """ /re/ enforce re instead of glob """
      pat = pat[1:-1]
    else:
      p = fnmatch.translate(pat)
      pat = p[:-7] # strip \Z(?ms)

    filepat = re.compile(pat, _arg_re_flags)
    for d in args[1:]:
      do_glob(filepat, d)

  elif _search_kind == "tags":
    """ args should be tagfile filepattern - mytags.tag f:main"""
    if len(args) != 2 or args[1].find(":") == -1:
      usage()

    (scope, ident) = args[1].split(":")
    if scope not in known_scopes_:
      print "Unknown scope: %s" % kind
      usage()

    try:
      do_ctags(args[0], scope, ident)
    except IOError as ex:
      print "Unable to open tagfile (%s)" % str(ex)

  else:
    fatal("No search kind specified should be either -e (grep) or -g (glob)")
    sys.exit(7)

  sys.exit(0)
