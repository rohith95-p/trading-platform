"""Replay the supplied Aurion EX5 in a dedicated portable MT5 Strategy Tester."""
import argparse
from html import escape
from pathlib import Path
import re
import shutil
import subprocess
from uuid import uuid4
from zipfile import ZipFile

from scripts.research.luna_six_month_audit import read_report


def run(package, terminal, start, end, name, leverage, output):
    prefix = "Aurion MT5 BOT Files-Trial/"
    with ZipFile(package) as bundle:
        expert = bundle.read(prefix + "Aurion_MT5.ex5")
        settings = bundle.read(prefix + "LowRisk-Aurion.set")
    preset = settings.decode("utf-16")
    private_inputs = [
        key.strip() for key in re.findall(r"(?im)^licensekey\s*=\s*([^\r\n]+)", preset)
        if key.strip() not in ("", "-", "0")
    ]
    identifier = f"Aurion_{uuid4().hex}"
    experts = terminal / "MQL5/Experts/AurionResearch"
    presets = terminal / "MQL5/Profiles/Tester"
    experts.mkdir(parents=True, exist_ok=True)
    presets.mkdir(parents=True, exist_ok=True)
    (experts / "Aurion_MT5.ex5").write_bytes(expert)
    (presets / f"{identifier}.set").write_bytes(settings)
    template = (terminal / "arch48_default.ini").read_text(encoding="utf-8-sig")
    for key, value in {
        "Expert": r"AurionResearch\Aurion_MT5.ex5", "ExpertParameters": identifier + ".set",
        "Report": identifier, "FromDate": start, "ToDate": end, "Leverage": leverage,
    }.items():
        template, count = re.subn(rf"(?m)^{key}=.*$", lambda _: f"{key}={value}", template)
        if count != 1:
            raise ValueError(f"Expected one {key} setting")
    for line in ("Enabled=0", "AllowDllImport=0", "AllowLiveTrading=0", "UseRemote=0",
                 "UseCloud=0", "Model=4", "Symbol=XAUUSDm.L48", "Period=M15"):
        if line not in template.splitlines():
            raise ValueError(f"Unexpected tester configuration, missing {line}")
    cfg = terminal / f"{identifier}.ini"
    cfg.write_text(template, encoding="utf-8")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    subprocess.run([str(terminal / "terminal64.exe"), "/portable", f"/config:{cfg}"],
                   cwd=terminal, startupinfo=startup, check=True)
    publish(terminal, identifier, start, end, name, leverage, output, private_inputs)


def publish(terminal, identifier, start, end, name, leverage, output, private_inputs):
    original = terminal / f"{identifier}.htm"
    if not original.is_file():
        raise RuntimeError("MT5 produced no native report")
    stats, deals = read_report(original)
    if stats.get("Period") != f"M15 ({start} - {end})" or stats.get("Leverage") != leverage:
        raise RuntimeError("MT5 report does not contain the requested period and leverage")
    output.mkdir(parents=True, exist_ok=True)
    html = original.read_text(encoding="utf-16").replace(identifier, name)
    for private in private_inputs:
        html = html.replace(private, "[redacted]").replace(escape(private), "[redacted]")
    (output / f"{name}.htm").write_text(html, encoding="utf-16")
    for graph in terminal.glob(f"{identifier}*.png"):
        shutil.copyfile(graph, output / graph.name.replace(identifier, name))
    print(name, stats, len(deals), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("package", type=Path)
    p.add_argument("terminal", type=Path)
    p.add_argument("start")
    p.add_argument("end")
    p.add_argument("name")
    p.add_argument("--leverage", default="1:100", choices=["1:100", "1:50"])
    p.add_argument("--output", default=Path("research/results/aurion_mt5_trial"), type=Path)
    run(**vars(p.parse_args()))
