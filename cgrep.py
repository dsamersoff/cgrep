#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import os
import sys
import getopt
import signal

import re
import fnmatch

HELP = """
 Advanced grep tool that can:

 find a file recursively:
   cgrep -g[is] -x exclude filename_glob dir1 dir2

 find pattern in file
   cgrep -e -x exclude filename_glob dir

 scoped find (ctags support)
   cgrep -t filename.tag scope:pattern
  Use:
    find . -name "*.[ch]" | ctags -L - -f tagfile
"""


""" Parameters """
_skip_dir = [".hg", ".git", ".svn", "CVS", "RCS", "SCCS"]
_skip_ext = [".bin", ".o", ".obj", ".class", ".so", ".dynlib", ".dll", ".zip", ".jar", ".gz", ".gch", ".pch", ".pdb", ".swp", ".jpg", ".ttf"]
_max_line_part = 40

_arg_re_flags = 0
_arg_dirsonly = False
_arg_word = False
_arg_warn_skip = True
_arg_no_skip = False
_arg_context = False

""" global varables """

_search_kind = None

_extra_skip_dir = []
_extra_skip_ext = []
_extra_skip_re = []


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

  def cl(self, color=None, msg=""):
    if not self.enabled:
      return msg

    if color is None or color == "/":
      return "\033[0m"

    if msg != "":
      return "\033[%dm%s\033[0m" % (Color.ANSI_COLORS[color], msg)

    return "\033[%dm" % Color.ANSI_COLORS[color]

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

  (fname, ext) = os.path.splitext(filename) #pylint: disable=unused-variable
  if ext in _skip_ext:
    return True

  if ext in _extra_skip_ext:
    return True
  return False

def lineno_file(filename, lineno):
  line_count = 0
  good_lines = []
  kp = (0, "")
  with open(filename, "r") as fd:
    for ln in fd:
      line_count += 1
      if line_count == lineno:
        good_ln = _color.cl("green") + ln + _color.cl("/")
        if _arg_context:
          good_lines.append(kp)
          good_lines.append((line_count, good_ln))
          good_lines.append((line_count + 1, next(fd, '')))
        else:
          good_lines.append((line_count, good_ln))
      kp = (line_count, ln[:-1])
  return good_lines

def grep_file(filename, pattern):
  line_count = 0
  good_lines = []
  kp = (0, "")
  with open(filename, "r") as fd:
    for ln in fd:
      line_count += 1
      m = pattern.search(ln)
      if m != None:
        a = m.string[:m.start(0)]
        b = m.string[m.start(0):m.end(0)]
        c = m.string[m.end(0):]
        if len(a) > _max_line_part:
          a = "..." + a[len(a)-_max_line_part:]
        if len(c) > _max_line_part:
          c = c[:_max_line_part] + "..."
        good_ln = a + _color.cl("green") + b + _color.cl("/") + c[:-1]
        if _arg_context:
          good_lines.append(kp)
          good_lines.append((line_count, good_ln))
          good_lines.append((line_count + 1, next(fd, '')))
        else:
          good_lines.append((line_count, good_ln))
      kp = (line_count, ln[:-1])
  return good_lines

def do_grep(filepattern, textpattern, dirname):
  for root, dirs, files in os.walk(dirname, topdown=True):
    for name in dirs:
      fn = os.path.join(root, name)
      (flag, text) = should_skip_dir(name)
      if flag:
        dirs.remove(name)
        if text != None and _arg_warn_skip:
          print _color.cl("magenta", "Skipped (%s) %s " % (text, fn))
        continue
    for name in files:
      if filepattern.search(name):
        fn = os.path.join(root, name)
        if should_skip_file(name):
          continue
        try:
          good_lines = grep_file(fn, textpattern)
          if len(good_lines) > 0:
            print _color.cl("yellow", fn)
            for (n, l) in good_lines:
              print "%4d: %s" % (n, l)
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
          print _color.cl("magenta", "Skipped [%s] %s" % (text, fn))
        continue
      if pattern.search(name):
        print _color.cl("yellow", fn)
    if _arg_dirsonly:
      continue

    for name in files:
      if pattern.search(name):
        fn = os.path.join(root, name)
        if not should_skip_file(name):
          print fn

def parse_tag_line(ln, kind, ident):
  if ln.find(kind) == -1:
    """ Kind quick check it shopuld be prepared ';"\t'+kind"""
    return (None, None, None, None)

  i1 = ln.index("\t")
  tagname = ln[0:i1]

  if re.match(ident, tagname) is None:
    return (None, None, None, None)

  i2 = ln.index("\t", i1 + 1)
  srcfile = ln[i1 + 1:i2]

  lineno = None
  pattern = None
  if ln[i2 + 1] == '/':
    i3 = ln.index('$/;', i2 + 2)
    pattern = re.sub(r"([()*\[\]])", r"\\\1", ln[i2 + 2:i3 + 1])
  else:
    i3 = ln.index(';', i2 + 2)
    lineno = int(ln[i2:i3])

  return (tagname, srcfile, pattern, lineno)

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
                               "hcegdisSux:t",
                               ["help", "color", "grep", "glob", "dirsonly", "ignorecase", "warnskip", "noskip", "context", "exclude", "tags"])
  except getopt.GetoptError as err:
    print str(err)
    usage()

  extra_skip = list()

  for o, a in opts:
    if o in ("-c", "--color"):
      """Use ansy color on printing"""
      _color.disable()
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
    elif o in ("-h", "--help"):
      usage()
    else:
      assert False, "unhandled option"

  if len(args) == 0:
    usage()

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
    if len(args) != 2:
      usage()

    (kind, ident) = args[1].split(":")
    """ Hacks, move it off loop """
    kind = ';"\t' + kind
    ident_re = re.compile(ident, _arg_re_flags)

    with open(args[0], "r") as tagf:
      for ln in tagf:
        (tagname, srcfile, tagpattern, lineno) = parse_tag_line(ln, kind, ident)
        if tagname != None:
          if lineno != None:
            good_lines = lineno_file(srcfile, lineno)
          else:
            # print "%d:/%s/" % (line_count, tagpattern)
            tag_re = re.compile(tagpattern)
            good_lines = grep_file(srcfile, tag_re)

          if len(good_lines) > 0:
            print _color.cl("yellow", srcfile)
            for (n, l) in good_lines:
              print "%4d: %s" % (n, l)
  else:
    fatal("No search kind specified should be either -e (grep) or -g (glob)")
    sys.exit(7)

  sys.exit(0)
