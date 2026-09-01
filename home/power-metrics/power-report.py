#!/usr/bin/env python3
"""Turn power-sample.sh CSV into the numbers a UPS purchase actually needs.

The 2026-09-01 sizing note used two spot readings plus a duty cycle inferred from log
timestamps. This reports it from data instead, and separates the two figures that get
conflated:

  PEAK  decides whether the UPS can carry the load AT ALL. A UPS that overloads
        drops its load instead of transferring to battery, so the peak is what
        determines whether you get protection or an abrupt cut.
  AVERAGE decides RUNTIME. On a bursty workload (this box is ~2-3% duty cycle
        serving a public portfolio chat) average draw is far below peak, so runtime
        is much better than a peak-based estimate suggests.

Sizing on peak alone over-buys; sizing on average alone buys a UPS that fails in the
one moment it is needed. You need both.

Privacy: reads only the metadata CSV — watts, temps, utilisation. No request content
exists in that file (red-lines.md #2).

Usage:
    power-report.py [csv]                  # default /var/log/power-metrics.csv
    power-report.py --psu-efficiency 0.90  # DC -> AC at the wall
    power-report.py --busy-watts 250       # GPU total above this counts as "busy"
"""
import argparse
import csv
import sys


def pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(len(s) * p))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?", default="/var/log/power-metrics.csv")
    ap.add_argument("--psu-efficiency", type=float, default=0.90,
                    help="component DC draw -> AC at the wall (default 0.90)")
    ap.add_argument("--busy-watts", type=float, default=250.0,
                    help="GPU total above this counts as a generation burst")
    ap.add_argument("--other-watts", type=float, default=80.0,
                    help="RAM/drives/fans/board not covered by GPU or RAPL")
    args = ap.parse_args()

    try:
        rows = list(csv.DictReader(open(args.csv)))
    except FileNotFoundError:
        print(f"no samples yet at {args.csv}", file=sys.stderr)
        return 1
    if not rows:
        print("no samples yet", file=sys.stderr)
        return 1

    def nums(key):
        out = []
        for r in rows:
            try:
                out.append(float(r[key]))
            except (ValueError, KeyError, TypeError):
                pass
        return out

    gpu = nums("gpu_total_w")
    cpu = nums("cpu_pkg_w")
    if not gpu:
        print("no usable GPU samples", file=sys.stderr)
        return 1

    ts = nums("ts_unix")
    span_h = (max(ts) - min(ts)) / 3600 if len(ts) > 1 else 0.0
    busy = [w for w in gpu if w >= args.busy_watts]
    duty = len(busy) / len(gpu) * 100

    cpu_avg = sum(cpu) / len(cpu) if cpu else 0.0
    cpu_peak = max(cpu) if cpu else 0.0

    def wall(dc):
        return dc / args.psu_efficiency

    avg_dc = sum(gpu) / len(gpu) + cpu_avg + args.other_watts
    peak_dc = max(gpu) + cpu_peak + args.other_watts

    print(f"samples: {len(gpu)} over {span_h:.1f}h   ({args.csv})")
    print()
    print("GPU total (both cards)")
    print(f"  min {min(gpu):6.1f} W   median {pct(gpu,0.5):6.1f} W   "
          f"p95 {pct(gpu,0.95):6.1f} W   max {max(gpu):6.1f} W")
    if cpu:
        print(f"CPU package: avg {cpu_avg:.1f} W   max {cpu_peak:.1f} W")
    print()
    print(f"duty cycle (GPU total >= {args.busy_watts:.0f} W): "
          f"{duty:.1f}%  ({len(busy)}/{len(gpu)} samples)")
    if span_h > 0:
        print(f"  -> roughly {duty/100*span_h*60:.0f} min busy per {span_h:.1f}h observed")
    print()
    print(f"WHOLE BOX at the wall (PSU eff {args.psu_efficiency:.2f}, "
          f"+{args.other_watts:.0f} W for RAM/drives/fans)")
    print(f"  average : {wall(avg_dc):6.0f} W   <- governs RUNTIME")
    print(f"  peak    : {wall(peak_dc):6.0f} W   <- governs whether the UPS carries it at all")
    print()
    for rating in (330, 900, 1000):
        load_pk = wall(peak_dc) / rating * 100
        load_av = wall(avg_dc) / rating * 100
        verdict = ("OVERLOADED at peak" if load_pk >= 100 else
                   "tight (>80% peak)" if load_pk > 80 else "ok")
        print(f"  vs {rating:4d} W UPS: peak {load_pk:5.1f}%  avg {load_av:5.1f}%   {verdict}")
    print()
    print("Reminder: runtime follows the AVERAGE, but a UPS that overloads on a burst")
    print("drops the load instead of transferring — so the peak decides whether you get")
    print("protection at all. Size for peak; expect runtime from average.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
