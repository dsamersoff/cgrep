#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: expandtab shiftwidth=2 softtabstop=2

# version 1.01 2020-04-29

_HELP="""
    ....
  """

import os
import sys
import getopt
import signal
import traceback
import re
import fnmatch
import codecs

_verbosity = 9
_max_line_part = 40
_show_context = False
_out_fd = None 
_colors_enabled = True
_re_flags = 0


""" Parameters """
_dirs_to_skip = [".hg", ".git", ".svn", "CVS", "RCS", "SCCS"]
_files_to_skip = ["*.exe", "*.bin", "*.so", "*.dynlib", "*.dll", "*.a",
                  "*.o", "*.obj", "*.class",
                  "*.zip", "*.jar", "*.gz",
                  "*.gch", "*.pch", "*.pdb", "*.swp", "*.icu",
                  "*.jpg", "*.ttf", "*.gif", "*png", "*.tiff", "*.ico"]

_extra_skip = []
_skiplist_files = [".cgrepignore", "~/.cgrepignore", "~/.config/cgrep/ignore"]

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
  return list(filter(lambda x: x not in _dirs_to_skip, dirlist))

def filelist_filter(filelist, filepatter):
  return filelist  

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

""" grep search """
def do_grep(filepattern, textpattern, dirname):
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
                                "h",
                               ["help"])
  except getopt.GetoptError as ex:
    usage(ex)

  for o, a in opts:
    if o in ("-h", "--help"):
      usage()
    else:
      assert False, "unhandled option"

  if not sys.stdout.isatty():
    """ output is redirected, disable colors """
    _colors_enabled = False

  """ Validate parameters before actual run """
  try:
    pass
  except Exception as ex:
    usage(ex)  

  """ Load skiplists """
  for fn in _skiplist_files:
    fns = os.path.expanduser(fn)
    if os.path.exists(fns):
      with open_uf(fns, "r") as ifd:
        for ln in ifd:
          _extra_skip.append(ln[:-1])

  """ Run grep """
  """ args should be textpattern filepattern1 filepatternN"""
  if len(args) == 1:
    """ only textpattern present """
    args.append("*")

  textpat = re.compile(args[0], _re_flags)

  """ file pattern is glob and case sensitive """
  for filepat in args[1:]:
    do_grep(filepat, textpat, ".")