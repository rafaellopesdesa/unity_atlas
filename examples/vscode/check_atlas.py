"""Run with VS Code's Run button, debugger, and notebook kernel."""
import os
import sys
from pathlib import Path

import ROOT

ROOT.gROOT.SetBatch(True)
print(Path("/etc/os-release").read_text())
print("Python:", sys.executable)
print("ATLAS project:", os.environ.get("AtlasProject"))
print("ATLAS version:", os.environ.get("AtlasVersion"))
print("ROOT:", ROOT.gROOT.GetVersion())
print("CUDA_VISIBLE_DEVICES:", os.environ.get("CUDA_VISIBLE_DEVICES"))
histogram = ROOT.TH1D("check", "VS Code ATLAS check", 10, 0, 10)
histogram.Fill(4.0)  # Put a breakpoint here.
print("Entries:", histogram.GetEntries())
assert histogram.GetEntries() == 1
