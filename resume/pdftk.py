# Python interface to the pdftk command-line tool
# 
import subprocess
import re

class PDF:

  numPagesRe = re.compile("NumberOfPages: (\\d+)")
  
  def __init__(self,path):
    self.path = path

  def allInfo(self):
    p = subprocess.Popen(["pdftk",self.path,"dump_data"],stdout=subprocess.PIPE,
                         close_fds=True)
    p.wait() # not much output, so this should not deadlock
    r = p.stdout.read()
    p.stdout.close()
    return r
 
  def get_numPages(self):
    all = self.allInfo()
    return int(PDF.numPagesRe.search(all).groups(1)[0])
  
  numPages = property(fget = get_numPages)
