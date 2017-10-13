# cgrep

This project is an advanced grep utility optimized for programmers. This utility written purely in a python.

cgrep operates in tree different modes:
  -g File finding mode
  -e Regex search mode
  -t Tagged search mode


Flags supported in all modes:

-c Turn off color output (color output disabled by default on MS Windows)
-i Ignore case
-s Don't warn about skipped files
-S Ignore build-in skip list
-o Output resul
-x Exclude file/dir matched pattern from search


## File finding mode (-g)

In this mode cgrep recursively searches through list of files and display files that matches **glob** expression.

```
  #cgrep -g -x "*i386*" stack
  Skipped ./.git
  ./src/stackFrame.h
  ./src/stackFrame_aarch64.cpp
  ./src/stackFrame_arm.cpp
  ./src/stackFrame_x64.cpp
```
flags supported in this mode:
  -d Search directories only
