# Reproduce the real recording

The committed GIF is a recording of `scripts/demo.py` driving the running kind cluster.
It uses asciinema 2.4.0 in WSL, Windows PowerShell for the actual command, and agg 1.9.0
to render the recording. No simulated terminal output is used.

1. Run the Windows quick start and confirm the local platform works.
2. Install asciinema and agg using their official releases, or download them into `.tools/`.
3. In WSL, run a real recording of the Windows command (adjust the checkout path):

   ```bash
   asciinema rec --cols 110 --rows 30 --overwrite \
     -c "pwsh.exe -NonInteractive -NoProfile -File 'H:\My Projects - IT\platform-delivery-lab\scripts\demo-terminal.ps1'" \
     demo.cast
   ```

4. Render in PowerShell:

   ```powershell
   agg --theme github-dark --font-size 16 --speed 3 --idle-time-limit 1000 --last-frame-duration 5 --cols 80 --rows 24 demo.cast docs/demo.gif
   ```

The 3× playback preserves idle periods and all command output. Full-speed elapsed time
is recoverable from the timestamps in the JSON evidence. GIF playback duration is measured
and reported in the evidence index. Raw cast recordings are ignored to avoid committing
terminal environment metadata accidentally.

`python scripts/capture.py` uses Playwright to submit a real synthetic ticket and capture
the browser console and the provisioned Grafana dashboard. It requires the optional Chromium
runtime (`python -m playwright install chromium`). Screenshot files are not UI mockups.

References: [asciinema](https://docs.asciinema.org/manual/cli/),
[agg](https://docs.asciinema.org/manual/agg/),
[Argo analysis](https://argoproj.github.io/argo-rollouts/features/analysis/),
[NGINX traffic routing](https://argoproj.github.io/argo-rollouts/features/traffic-management/nginx/),
[Terraform kind provider](https://registry.terraform.io/providers/tehcyx/kind/0.11.0/docs/resources/cluster).
