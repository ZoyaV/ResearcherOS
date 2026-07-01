"""Диагностика: открывается ли облачный USD и куда зеркалируются ассеты."""
from isaaclab.app import AppLauncher

app = AppLauncher(headless=True).app

import glob
import os

import omni.client

URL = (
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com"
    "/Assets/Isaac/6.0/Isaac/Environments/Grid/default_environment.usd"
)
res, _ = omni.client.stat(URL)
print("omni.client.stat:", res)

from pxr import Usd

stage = Usd.Stage.Open(URL)
print("Usd.Stage.Open ok:", bool(stage))

tmp = os.environ.get("TMPDIR", "/tmp")
print("TMPDIR:", tmp)
print("mirror files:", glob.glob(os.path.join(tmp, "Assets", "**", "*.usd"), recursive=True)[:3])
app.close()
