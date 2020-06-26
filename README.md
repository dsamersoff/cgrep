# cgrep

This project is an advanced grep utility with ANSI coloring, optimized for code inspection. 
This utility written purely in a python.

  Find a file recursively:

    cgrep -o outfile -g[i] filename_glob dir1 dirN

  Find pattern in file

    cgrep -o outfile -e[i] text_pattern file_pattern1 file_patternN

  Scoped identifier search (ctags)

    cgrep -o outfile -t filename.tag scope:pattern

### Examples:

    cgrep.py -o cgrep_test.log dlopen

    cgrep.py -O cgrep_test.log "dlopen_.*\(const"

    cgrep.py -t .tags e:ACCESS_OK

    cgrep.py -gRi "linux_aarch*" 

    cgrep.py -gi "linux_aarch" 

### Additional Flags:

-i      - ignorecase

-C      - turn off coloring

-d      - utility debugging 

-o file - duplicate output to a file

-O file - redirect output to a file 

-r      - use regexp for file searching

-R      - use shell-matching for file searching

-x list - add items to file skip list, e.g. "*.md:*ignore"

-X list - replace file skip list with items

-S      - turn off file and directory skipping

### Tips:
Build tag file:

    ctags -R --c++-types=+px --extra=+q --excmd=pattern --exclude=Makefile --exclude=.tags -f .tags

Use files to add more items to default skip: .cgrepignore ~/.cgrepignore or ~/.config/cgrep/ignore

