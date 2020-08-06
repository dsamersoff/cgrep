#!/bin/sh
PYTHON=/c/Users/812426/AppData/Local/Programs/Python/Python38/python.exe
HOTSPOT=/c/Users/812426/Export/ojdk/jdk14/src/hotspot
CWD=`pwd`

if [ -f $CWD/cgrep_test.log ]
then
  rm $CWD/cgrep_test.log 
fi  

cd $HOTSPOT

if [ ! -f $CWD/.tags ]
then
  ctags -R --c++-types=+px --extra=+q --excmd=pattern --exclude=Makefile --exclude=.tags -f $CWD/.tags
fi

$PYTHON $CWD/cgrep.py -V >> $CWD/cgrep_test.log 
ret=$?
if [ $ret -eq 7 ]; then
  echo "BOTSTRAP OK"
  cat $CWD/cgrep_test.log 
else
  echo "BOOTSTRAP FAILED expected 7 got $ret"
fi  

echo "###### TEST 1 GREP" >> $CWD/cgrep_test.log 
$PYTHON $CWD/cgrep.py -O $CWD/cgrep_test.log dlopen
ret=$?
if [ $ret -eq 34 ]; then
  echo "TEST PASSED"
else
  echo "TEST FAILED expected 34 got $ret"
fi  

echo "###### TEST 2 GREP" >> $CWD/cgrep_test.log 
$PYTHON $CWD/cgrep.py -O $CWD/cgrep_test.log "dlopen_.*\(const"
ret=$?
if [ $ret -eq 2 ]; then
  echo "TEST PASSED"
else
  echo "TEST FAILED expected 2 got $ret"
fi  

echo "###### TEST 3 TAG" >> $CWD/cgrep_test.log 
$PYTHON $CWD/cgrep.py -O $CWD/cgrep_test.log -t $CWD/.tags e:ACCESS_OK
ret=$?
if [ $ret -eq 1 ]; then
  echo "TEST PASSED"
else
  echo "TEST FAILED expected 2 got $ret"
fi  

echo "###### TEST 4 GLOB" >> $CWD/cgrep_test.log 
$PYTHON $CWD/cgrep.py -O $CWD/cgrep_test.log -gRi "linux_aarch*" 
ret=$?
if [ $ret -eq 17 ]; then
  echo "TEST PASSED"
else
  echo "TEST FAILED expected 2 got $ret"
fi  

echo "###### TEST 5 GLOB" >> $CWD/cgrep_test.log 
$PYTHON $CWD/cgrep.py -O $CWD/cgrep_test.log -gi "linux_aarch" 
ret=$?
if [ $ret -eq 17 ]; then
  echo "TEST PASSED"
else
  echo "TEST FAILED expected 2 got $ret"
fi  