#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import getopt
import signal
import traceback
import codecs
import locale

import re
import fnmatch

VERSION = "4.002 2020-06-24"

HELP = """
  Advanced grep tool that can:

  find a file recursively:
    cgrep -o outfile -g[is] -x exclude filename_glob dir1 dir2

  find pattern in file
    cgrep -o outfile -e -x exclude filename_glob dir

  scoped find (ctags support)
    cgrep -t filename.tag scope:pattern
    (.tags used by default, scope: p - prototype, f - function, c - class, s - struct, m - member, t - type)

  Tips:
    Build tag file:
      ctags -R --c++-types=+px --extra=+q --excmd=pattern --exclude=Makefile --exclude=.tags -f .tags
    Use files to add more items to default skip: .cgrepignore ~/.cgrepignore or ~/.config/cgrep/ignore
"""

""" Parameters """
_dirs_to_skip = [".hg", ".git", ".svn", "CVS", "RCS", "SCCS"]
_files_to_skip = ["*.exe", "*.bin", "*.so", "*.dynlib", "*.dll", "*.a",
                  "*.o", "*.obj", "*.class",
                  "*.zip", "*.jar", "*.gz",
                  "*.gch", "*.pch", "*.pdb", "*.swp", "*.icu",
                  "*.jpg", "*.ttf", "*.gif", "*png", "*.tiff", "*.ico"]

_extra_skip = []

_skip_files = [".cgrepignore", "~/.cgrepignore", "~/.config/cgrep/ignore"]

_max_line_part = 40

_arg_re_flags = 0
_arg_dirsonly = False
_arg_word = False
_arg_warn_skip = False
_arg_no_skip = False
_arg_context = False
_arg_outfile = None
_arg_debug_cgrep = False

""" global varables """

_search_kind = "grep"

_out_fd = None

_known_scopes = ["p","f","c","s","m","t"]
_default_tagfile = ".tags"

def report_exception(msg, ex):
  """ Report exception """
  print(_color.cl("magenta", msg + "(%s)" % str(ex)))
  if _arg_debug_cgrep:
    print(traceback.format_exc())

def open_uf(filename, mode):
  """ Open text file with encoding support """
  return codecs.open(filename, mode, "utf_8_sig", errors='ignore')

""" Fancy printing """
class Color(object):
  COLOR = "\033[%dm%s\033[0m"
  ANSI_COLORS = {"default" : 0, "black" : 30, "red" : 31, "green" : 32,
                 "yellow" : 33, "blue" : 34, "magenta" : 35, "cyan" : 36,
                 "white" : 37}

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
  
  def eol(self, need_eol):
    if need_eol:
      return "\n"
    return ""

  def prn(self, color, msg, need_eol = True):
    if _out_fd != None:
      _out_fd.write(msg + self.eol(need_eol))
    sys.stdout.write(self.cl(color, msg) + self.eol(need_eol))

  def prncon(self, color, msg, need_eol = True):
    sys.stdout.write(self.cl(color, msg) + self.eol(need_eol))

  def ref(self, color, msg, filename):
    if _out_fd != None:
        _out_fd.write(msg + "\n")
    sys.stdout.write(self.cl(color, msg) + "\n")

_color = Color()

def should_skip(name, skip_list):
  """ Check additional skip conditions """
  if _arg_no_skip:
    return False

  """ Hardcoded skip, shell pattern match """
  matched = [x for x in skip_list if fnmatch.fnmatch(name, x)]
  if len(matched) > 0:
    return True

  matched = [x for x in _extra_skip if fnmatch.fnmatch(name, x)]
  return len(matched) > 0

def should_skip_dir(dirname):
  return should_skip(dirname, _dirs_to_skip)

def should_skip_file(filename):
  return should_skip(filename, _files_to_skip)

def grep_file(filename, pattern):
  line_count = 0
  good_lines = []
  kp = (0, "", "", "")
  with open_uf(filename, "r") as fd:
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
      if should_skip_dir(name):
        dirs.remove(name)
        if _arg_warn_skip:
          _color.prncon("magenta", "Skipped %s" % name)
        continue
      fn = os.path.join(root, name)
    for name in files:
      if filepattern.search(name):
        fn = os.path.join(root, name)
        if should_skip_file(name):
          if _arg_warn_skip:
            _color.prncon("magenta", "Skipped %s " % fn)
          continue
        try:
          good_lines = grep_file(fn, textpattern)
          if len(good_lines) > 0:
            _color.ref("yellow", fn, os.path.abspath(fn))
            for good_line in good_lines:
              print_good_line(good_line)
        except Exception as ex:
          report_exception(fn, ex)

""" filename search """
def do_glob(pattern, dirname):
  for root, dirs, files in os.walk(dirname, topdown=True):
    for name in dirs:
      fn = os.path.join(root, name)
      if should_skip_dir(name):
        dirs.remove(name)
        if _arg_warn_skip:
          _color.prncon("magenta", "Skipped %s" % fn)
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

""" Tagged search """
def parse_tag_line(p_ln, p_scope, p_ident_re):
  if p_ln.startswith("!"):
    """ Skip comments """
    return (None, None, None)

  try:
    (tagname, srcfile, tagpattern, scope) = p_ln.split("\t", 3)
  except ValueError as ex:
    report_exception("CTAGS line format error: '%s'" % ln, ex)
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
    report_exception("CTAGS re format error: '%s'" % tagpattern, ex)
    return (None, None, None)

  return (tagname, srcfile, tag_re)

def do_ctags(tagfile, scope, ident):
  ident_re = re.compile(ident, _arg_re_flags)
  found_lines = dict()

  with open_uf(tagfile, "r") as tagf:
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

""" Support function """
def fatal(msg, e=None):
  s = " (%s)" % str(e) if e != None else ""
  print(_color.cl("red", msg + s))
  sys.exit(-1)

def usage():
  print(HELP)
  sys.exit(7)

def signal_handler(signal, frame): #pylint: disable=unused-argument
  sys.stdout.write("\nInterrupted. Exiting ...\n")
  sys.exit(-1)

if __name__ == '__main__':
  """ set ctrl-C handler and reopen stdout unbuffered """
  signal.signal(signal.SIGINT, signal_handler)
  if not sys.stdout.isatty():
    """ output is redirected, disable colors """
    _color.disable()

  extra_skip = list()

  try:
    opts, args = getopt.getopt(sys.argv[1:],
                               "hcegdisSux:to:D",
                               ["help", "color", "grep", "glob", "dirsonly", "ignorecase", "warnskip", "noskip", "context", "exclude", "tags", "output", "debug"])
  except getopt.GetoptError as ex:
    report_exception("GetoptError", ex)
    usage()

  for o, a in opts:
    if o in ("-c", "--color"):
      _color.toggle()
    elif o in ("-e", "--grep"):
      _search_kind = "grep"
    elif o in ("-g", "--glob"):
      _search_kind = "glob"
    elif o in ("-t", "--tags"):
      _search_kind = "tags"
    elif o in ("-x", "--exclude"):
      _extra_skip += a.split(":")
    elif o in ("-d", "--dirsonly"): 
      _arg_dirsonly = True
    elif o in ("-i", "--ignorecase"):
      _arg_re_flags |= re.IGNORECASE
    elif o in ("-s", "--warnskip"):
      _arg_warn_skip = True
    elif o in ("-S", "--noskip"):
      _arg_no_skip = True
    elif o in ("-u", "--context"):
      _arg_context = True
    elif o in ("-o", "--output"):
      _arg_outfile = a
    elif o in ("-D", "--debug"):
      _arg_debug_cgrep = True
    elif o in ("-h", "--help"):
      usage()
    else:
      assert False, "unhandled option"

  """ Validate input parameters """
  if len(args) == 0:
    usage()

  """ Read skip from file """
  for fn in _skip_files:
    fns = os.path.expanduser(fn)
    if os.path.exists(fns):
      with open_uf(fns, "r") as ifd:
        for ln in ifd:
          _extra_skip.append(ln[:-1])

  filepat = None
  textpat = None
  
  if _arg_outfile != None:
    """ Redirect all output to file. Rely on OS to close it,
        append the file to skip list to avoid recursion
    """
    _arg_outfile = os.path.abspath(_arg_outfile)
    _files_to_skip.append(_arg_outfile)
    _out_fd = open(_arg_outfile, "w")
    
  if _search_kind == "grep":
    """ args should be textpattern filepattern1 filepatternN"""
    if len(args) == 1:
      """ only textpattern present """
      args.append("*")

    textpat = re.compile(args[0], _arg_re_flags)

    """ file pattern is glob and case sensitive """
    for filepat in args[1:]:
      p = re.compile(fnmatch.translate(filepat))
      do_grep(p, textpat, ".")

  elif _search_kind == "glob":
    """ args should be filepattern dir1 ... dirN"""
    if len(args) == 1:
      """ dirlist is missed """
      args.append(".")

    filepat = re.compile(fnmatch.translate(args[0]), _arg_re_flags)
    for d in args[1:]:
      do_glob(filepat, d)

  elif _search_kind == "tags":
    """ args should be tagfile filepattern - mytags.tag f:main"""
    if len(args) == 1:
      args.insert(0, _default_tagfile)

    assert len(args) == 1 or len(args) == 2, "Invalid number of arguments"
    assert args[1].find(":") != -1, "Invalid tag search format %s, should be scope:ident" % args[1]

    (tagfile, search) = (args[0], args[1])
    (scope, ident) = search.split(":")

    assert scope in _known_scopes, "Invalid tag search scope %s" % scope
    do_ctags(tagfile, scope, ident)

  sys.exit(0)
