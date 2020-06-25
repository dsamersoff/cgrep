#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: expandtab shiftwidth=2 softtabstop=2

# version 1.01 2020-04-29

_HELP="""
  Advanced grep tool that can:

  Find a file recursively:
    cgrep -o outfile -g[i] filename_glob dir1 dirN

  Find pattern in file
    cgrep -o outfile -e[i] text_pattern file_pattern1 file_patternN

  Scoped find (ctags)
    cgrep -o outfile -t filename.tag scope:pattern
    (.tags used by default, scope: p - prototype, f - function, c - class, s - struct, m - member, t - type)

  Tips:
    Build tag file:
      ctags -R --c++-types=+px --extra=+q --excmd=pattern --exclude=Makefile --exclude=.tags -f .tags
    Use files to add more items to default skip: .cgrepignore ~/.cgrepignore or ~/.config/cgrep/ignore

  TODO: 
    Return code from grep
  """

import os
import sys
import getopt
import signal
import traceback
import re
import codecs
import fnmatch

from enum import Enum

_dirs_to_skip = [".hg", ".git", ".svn", "CVS", "RCS", "SCCS"]
_files_to_skip = ["*.exe", "*.bin", "*.so", "*.dynlib", "*.dll", "*.a",
                  "*.o", "*.obj", "*.class",
                  "*.zip", "*.jar", "*.gz",
                  "*.gch", "*.pch", "*.pdb", "*.swp", "*.icu",
                  "*.jpg", "*.ttf", "*.gif", "*png", "*.tiff", "*.ico"]

_skiplist_files = [".cgrepignore", "~/.cgrepignore", "~/.config/cgrep/ignore"]


class RunMode(Enum):
  GREP = 1
  GLOB = 2
  TAG = 3

class SkipMode(Enum):
  ENABLED = 1
  OVERRIDE = 2
  DISABLED = 3

""" Defaults """
_verbosity = 9
_max_line_part = 40
_show_context = False
_colors_enabled = True
_re_flags = 0
_run_mode = RunMode.GREP 
_filepat_re = False

""" Globals """
_out_fd = None 
_output_name = None
_run_mode_default = True

_extra_skip = None
_skip_mode = SkipMode.ENABLED

# Color output support
class Color(object):
  COLOR = "\033[%dm%s\033[0m"
  ANSI_COLORS = {"default" : 0, "black" : 30, "red" : 31, "green" : 32,
                 "yellow" : 33, "blue" : 34, "magenta" : 35, "cyan" : 36,
                 "white" : 37}

  @staticmethod
  def cl(color=None, msg=""):
    """ Return ANSI colored message """
    global _colors_enabled

    if not _colors_enabled:
      return msg
    if color is None or color == "/":
      return "\033[0m"
    if msg != "":
      return "\033[%dm%s\033[0m" % (Color.ANSI_COLORS[color], msg)
    return "\033[%dm" % Color.ANSI_COLORS[color]
  
  @staticmethod
  def prn(color, msg):
    if _out_fd != None:  
      _out_fd.write(msg + "\n")
    sys.stdout.write(Color.cl(color, msg) + "\n")

  @staticmethod
  def prn_n(color, msg):
    if _out_fd != None:  
      _out_fd.write(msg)
    sys.stdout.write(Color.cl(color, msg))
## 

def open_uf(filename, mode):
  """ Open text file with encoding support """
  return codecs.open(filename, mode, "utf_8_sig", errors='ignore')

def report_exception(msg, ex):
  """ Report exception """
  Color.prn("magenta", msg + "(%s)" % str(ex))
  if _verbosity > 3:
    print(traceback.format_exc())

def print_good_lines(fn, good_lines):
  """ Print lines that match pattern """
  if good_lines:
    Color.prn("yellow", fn)
    for (n, a, b, c) in good_lines:
      if b != "" or c != "":
        if len(a) > _max_line_part:
          a = "..." + a[len(a) - _max_line_part:]
        if len(c) > _max_line_part:
          c = c[:_max_line_part] + "..."
     
        Color.prn_n("default", "%4d: %s" % (n, a))
        Color.prn_n("green", b)
        Color.prn("default", c)
      else:
        Color.prn("default", "%4d: %s" % (n, a))

def dirlist_filter(dirlist):
  global _dirs_to_skip
  if _dirs_to_skip:
    return list(filter(lambda x: x not in _dirs_to_skip, dirlist))
  return dirlist

def filelist_filter(filelist, filepattern):
  global _files_to_skip
  outlist = list(fnmatch.filter(filelist, filepattern))
  if _files_to_skip:
    outlist2 = list()
    for filename in outlist:
      res = [n for n in _files_to_skip if fnmatch.fnmatch(filename, n)]
      if not res:
        outlist2.append(filename)
    return outlist2    
  return outlist  

def grep_file(filename, pattern):
  """ Grep over the single file, store all matched lines into list"""
  line_count = 0
  good_lines = []
  prev_ln = (line_count, "", "", "")
  with open_uf(filename, "r") as fd:
    for ln in fd:
      line_count += 1
      m = pattern.search(ln)
      if m != None:
        (a, b, c) = (m.string[:m.start(0)], m.string[m.start(0):m.end(0)], m.string[m.end(0):-1])
        if _show_context and line_count > 1:
          good_lines.append(prev_ln)
        good_lines.append((line_count, a, b, c))
        if _show_context:
          good_lines.append((line_count + 1, next(fd, ''), "", ""))
      prev_ln = (line_count, ln, "", "")
  return good_lines

def do_grep(filepattern, textpattern, dirname):
  """ grep over the directories """
  for root, dirs, files in os.walk(dirname, topdown=True):
    dirs[:] = dirlist_filter(dirs)
    files[:] = filelist_filter(files, filepattern)
    for fname in files:
      fn = os.path.join(root, fname)
      try:
        good_lines = grep_file(fn, textpattern)
        print_good_lines(fn, good_lines)
      except Exception as ex:
        report_exception(fn, ex)

def do_glob(filepat_re, dirname):
  """ find files that names matches pattern """
  for root, dirs, files in os.walk(dirname, topdown=True):
    dirs[:] = dirlist_filter(dirs)
    for fname in files:
      m = filepat_re.search(fname)
      if m != None:
        (a, b, c) = (m.string[:m.start(0)], m.string[m.start(0):m.end(0)], m.string[m.end(0):])
        fn = os.path.join(root, fname)
        Color.prn_n("default", os.path.join(root, a)) 
        Color.prn_n("green", b)
        Color.prn("default", c)

def manage_skip_lists():
  """ Manage skiplists """
  global _dirs_to_skip, _files_to_skip, _skip_mode

  """ flush both dir and file skiplists if skip is disabled """
  if _skip_mode == SkipMode.DISABLED: 
    _dirs_to_skip = []

  elif _skip_mode == SkipMode.OVERRIDE or _skip_mode == SkipMode.DISABLED: 
    _files_to_skip = []

  elif _skip_mode == SkipMode.ENABLED: 
    """ Load additional skip list from user file """
    for fn in _skiplist_files:
      fns = os.path.expanduser(fn)
      if os.path.exists(fns):
        with open_uf(fns, "r") as ifd:
          for ln in ifd:
            _files_to_skip.append(ln[:-1])

def signal_handler(signal, frame): #pylint: disable=unused-argument
  sys.stdout.write("\nInterrupted. Exiting ...\n")
  sys.exit(-1)

def usage(msg=None):
  global _HELP
  if msg is not None:
    print ("Error: %s" % msg)
  print(_HELP)
  sys.exit(7)

if __name__ == '__main__':
  signal.signal(signal.SIGINT, signal_handler)

  try:
    opts, args = getopt.getopt(sys.argv[1:],
                                "ho:getiCSDrx:X:",
                               ["help", "output", "glob", "grep", "tag", "ignorecase", "no-color", "no-skip", "debug",\
                                "regexp", "exclude", "exclude-override"])
  except getopt.GetoptError as ex:
    usage(ex)

  for o, a in opts:
    if o in ("-h", "--help"):
      usage()
    elif o in ("-o", "--output"):
      _output_name = a
    elif o in ("-g", "--glob"):
      assert _run_mode_default, "Run mode already set"
      (_run_mode, _run_mode_default) = (RunMode.GLOB, False)
    elif o in ("-e", "--grep"):
      assert _run_mode_default, "Run mode already set"
      (_run_mode, _run_mode_default) = (RunMode.GREP, False)
    elif o in ("-t", "--tag"):
      assert _run_mode_default, "Run mode already set"
      (_run_mode, _run_mode_default) = (RunMode.TAG, False)
    elif o in ("-i", "--ignorecase"):
      _re_flags |= re.IGNORECASE
    elif o in ("-C", "--no-color"):
      _colors_enabled = False
    elif o in ("-S", "--no-skip"):
      _skip_mode = SkipMode.DISABLED
    elif o in ("-D", "--debug"):
      _verbosity = 9
    elif o in ("-r", "--regexp"):
      assert _run_mode == RunMode.GLOB, "Glob mode should be selected first"
      _filepat_re = True
    elif o in ("-x", "--exclude"):
      _extra_skip = a
    elif o in ("-X", "--exclude-override"):
      _extra_skip = a
      _skip_mode = SkipMode.OVERRIDE
    else:
      assert False, "Unhandled option '%s'" % o

  if not sys.stdout.isatty():
    """ output is redirected, disable colors """
    _colors_enabled = False

  if _output_name != None:
    _out_fd = open(_output_name, "w")

  """ Manage skiplists """
  manage_skip_lists()

  if _extra_skip != None:
    _files_to_skip += _extra_skip.split(":")

  print ("XXX: ", repr(_files_to_skip))    

  if _run_mode == RunMode.GREP:
    """ args should be textpattern filepattern1 filepatternN
        file pattern is glob and case sensitive
    """
    if len(args) == 1:
      """ Adding default filepattern if necessary """
      args.append("*")

    textpat = re.compile(args[0], _re_flags)
    for filepat in args[1:]:
      do_grep(filepat, textpat, ".")
    sys.exit(0)
      
  if _run_mode == RunMode.GLOB:
    if len(args) == 1:
      """ Adding default dir if necessary """
      args.append(".")

    filepat_re = args[0] if _filepat_re else fnmatch.translate(args[0])  
    if _verbosity > 3:
      print("Searching for: r'%s'" % filepat_re)  

    compiled_re = re.compile(filepat_re, _re_flags)  
    for dirname in args[1:]:
      do_glob(compiled_re, dirname)
    sys.exit(0)

  if _run_mode == RunMode.TAG:
    pass