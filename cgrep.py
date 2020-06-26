#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: expandtab shiftwidth=2 softtabstop=2

# version 5.102 2020-06-26

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

_known_scopes = ["p", "f", "c", "s", "m",
                 "t", "d", "e"]

class RunMode(Enum):
  GREP = 1
  GLOB = 2
  TAG = 3

class SkipMode(Enum):
  ENABLED = 1
  OVERRIDE = 2
  DISABLED = 3

""" Defaults (could be edited) """
_verbosity = 2
_max_line_part = 40
_show_context = False
_colors_enabled = True
_re_flags = 0
_run_mode = RunMode.GREP 
_filepat_re = True
_default_tagfile = ".tags"
_console_fd = sys.stdout

""" Globals (nothing to edit) """
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
  def cl(color, msg):
    """ Return ANSI colored message """
    global _colors_enabled
    if _colors_enabled:
      return "\033[%dm%s\033[0m" % (Color.ANSI_COLORS[color], msg)
    return msg  
  
  @staticmethod
  def prn_n(msg, color="default"):
    """ Print colored message, no eol """
    global _console_fd, _out_fd
    if _out_fd != None:  
      _out_fd.write(msg)
    if _console_fd != None:  
      _console_fd.write(Color.cl(color, msg))

  @staticmethod
  def prn(msg, color="default"):
    """ Print colored message """
    Color.prn_n(msg + "\n", color)
## 

def open_uf(filename, mode):
  """ Open text file with encoding support """
  return codecs.open(filename, mode, "utf_8_sig", errors='ignore')

def report_exception(msg, ex, exit_code=None):
  """ Report exception """
  Color.prn(msg + "(%s)" % str(ex), "magenta")
  if _verbosity > 3:
    Color.prn(traceback.format_exc())
  if exit_code != None:
    sys.exit(exit_code)  

def print_good_lines(fn, good_lines):
  """ Print lines that match pattern """
  if good_lines:
    Color.prn(fn, "yellow")
    for (n, a, b, c) in good_lines:
      if b != "" or c != "":
        if len(a) > _max_line_part:
          a = "..." + a[len(a) - _max_line_part:]
        if len(c) > _max_line_part:
          c = c[:_max_line_part] + "..."
     
        Color.prn_n("%4d: %s" % (n, a))
        Color.prn_n(b, "green")
        Color.prn(c)
      else:
        Color.prn("%4d: %s" % (n, a))

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

def get_tag(tagln, scope, ident_re):
  if not tagln.startswith("!"):
    try:
      (tagname, srcfile, tagpattern, tagscope) = tagln.split("\t", 3)
      if tagscope[0] == scope and ident_re.match(tagname) != None:
        tagpattern = tagpattern[1:-3] if tagpattern.endswith(';"') else tagpattern[1:-1]
        tagpattern = tagpattern.replace("(", "\\(").replace(")", "\\)")
        tag_re = re.compile(tagpattern[1:-3])
        return (tagname, srcfile, tag_re)
    except Exception as ex:
      report_exception("CTAGS line format error: '%s'" % tagln, ex)
  return (None, None, None)

# GREP Search for pattern within file
def grep_file(filename, pattern):
  """ Grep over the single file, store all matched lines into list"""
  line_count = 0
  found_count = 0
  good_lines = []
  prev_ln = (line_count, "", "", "")
  with open_uf(filename, "r") as fd:
    for ln in fd:
      line_count += 1
      m = pattern.search(ln)
      if m != None:
        found_count += 1
        (a, b, c) = (m.string[:m.start(0)], m.string[m.start(0):m.end(0)], m.string[m.end(0):-1])
        if _show_context and line_count > 1:
          good_lines.append(prev_ln)
        good_lines.append((line_count, a, b, c))
        if _show_context:
          good_lines.append((line_count + 1, next(fd, ''), "", ""))
      prev_ln = (line_count, ln, "", "")
  return (found_count, good_lines)

def do_grep(filepattern, textpattern, dirname):
  """ grep over the directories """
  total_found = 0
  for root, dirs, files in os.walk(dirname, topdown=True):
    dirs[:] = dirlist_filter(dirs)
    files[:] = filelist_filter(files, filepattern)
    for fname in files:
      fn = os.path.join(root, fname)
      try:
        (found, good_lines) = grep_file(fn, textpattern)
        total_found += found
        print_good_lines(fn, good_lines)
      except Exception as ex:
        report_exception(fn, ex)
  return total_found      

# TAG grep file using ctags tag file
def do_ctags(tagfile, scope, ident):
  """ grep over files using ctags patterns, no skips """
  global _re_flags
  ident_re = re.compile(ident, _re_flags)
  total_found = 0
  with open_uf(tagfile, "r") as tagf:
    for ln in tagf:
      (tagname, srcfile, tag_re) = get_tag(ln, scope, ident_re)
      if tagname != None:
        (found, good_lines) = grep_file(srcfile, tag_re)
        total_found += found
        print_good_lines(srcfile, good_lines)
  return total_found      

# GLOB Search for file name
def do_glob(filepat_re, dirname):
  """ find files that names matches pattern """
  found = 0
  for root, dirs, files in os.walk(dirname, topdown=True):
    dirs[:] = dirlist_filter(dirs)
    for fname in files:
      m = filepat_re.search(fname)
      if m != None:
        found += 1
        (a, b, c) = (m.string[:m.start(0)], m.string[m.start(0):m.end(0)], m.string[m.end(0):])
        fn = os.path.join(root, fname)
        Color.prn_n(os.path.join(root, a)) 
        Color.prn_n(b, "green")
        Color.prn(c)
  return found      

# Utility functions
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
                                "ho:O:getiCSdrRx:X:",
                               ["help", "output", "only-output" "glob", "grep", "tag", "ignorecase", "no-color", "no-skip", "debug",\
                                "regexp", "no-regexp", "exclude", "exclude-override"])
  except getopt.GetoptError as ex:
    usage(ex)

  for o, a in opts:
    if o in ("-h", "--help"):
      usage()
    elif o in ("-o", "--output"):
      _output_name = a
    elif o in ("-O", "--only-output"):
      _output_name = a
      _console_fd = None
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
    elif o in ("-d", "--debug"):
      _verbosity = 9
    elif o in ("-r", "--regexp"):
      assert _run_mode == RunMode.GLOB, "Glob mode should be selected first"
      _filepat_re = True
    elif o in ("-R", "--no-regexp"):
      assert _run_mode == RunMode.GLOB, "Glob mode should be selected first"
      _filepat_re = False
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
    _out_fd = open(_output_name, "a")

  """ Manage skiplists """
  manage_skip_lists()

  if _extra_skip != None:
    _files_to_skip += _extra_skip.split(":")

  if _run_mode == RunMode.GREP:
    try:
      """ args should be textpattern filepattern1 filepatternN
          file pattern is glob and case sensitive
      """
      assert len(args) > 0, "Arguments are required" 
      if len(args) == 1:
        """ Adding default filepattern if necessary """
        args.append("*")

      textpat = re.compile(args[0], _re_flags)
      found = 0
      for filepat in args[1:]:
        found += do_grep(filepat, textpat, ".")

      sys.exit(found)
    except Exception as ex:
      report_exception("GREP mode error", ex, -1)
        
  if _run_mode == RunMode.GLOB:
    try:
      assert len(args) > 0, "Arguments are required" 
      if len(args) == 1:
        """ Adding default dir if necessary """
        args.append(".")

      filepat_re = args[0] if _filepat_re else fnmatch.translate(args[0])  
      if _verbosity > 3:
        print("Searching for: r'%s'" % filepat_re)  

      found = 0
      compiled_re = re.compile(filepat_re, _re_flags)  
      for dirname in args[1:]:
        found += do_glob(compiled_re, dirname)
      sys.exit(found)
    except Exception as ex:
      report_exception("GLOB mode error", ex, -1)

  if _run_mode == RunMode.TAG:
    """ args should be tagfile filepattern - mytags.tag f:main"""
    try:
      assert len(args) == 1 or len(args) == 2, "Invalid number of arguments"
      if len(args) == 1:
        args.insert(0, _default_tagfile)

      assert args[1].find(":") != -1, "Invalid tag search format %s, should be scope:ident" % args[1]
      (scope, ident) = args[1].split(":")
      assert scope in _known_scopes, "Invalid tag search scope %s" % scope

      found = do_ctags(args[0], scope, ident)
      sys.exit(found)
    except Exception as ex:
      report_exception("TAG mode error", ex, -1)
