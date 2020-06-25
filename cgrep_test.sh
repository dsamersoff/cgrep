#!/bin/sh
PYTHON=/c/Users/812426/AppData/Local/Programs/Python/Python38/python.exe
HOTSPOT=/c/Users/812426/Export/ojdk/jdk14/src/hotspot
CWD=`pwd`

rm $CWD/cgrep5_test.log 

cd $HOTSPOT

echo "###### TEST 1" >> $CWD/cgrep5_test.log 
$PYTHON $CWD/cgrep5.py -O $CWD/cgrep5_test.log dlopen
ret=$?
if [ $ret -eq 34 ]; then
  echo "TEST PASSED"
else
  echo "TEST FAILED expected 34 got $ret"
fi  

echo "###### TEST 2" >> $CWD/cgrep5_test.log 
$PYTHON $CWD/cgrep5.py -O $CWD/cgrep5_test.log "dlopen_.*\(const"
ret=$?
if [ $ret -eq 2 ]; then
  echo "TEST PASSED"
else
  echo "TEST FAILED expected 2 got $ret"
fi  

 