# Cell-Free Transcription-Translation Simulator

A small deterministic simulator for exploring coupled cell-free transcription and translation kinetics. It includes a Python CLI/API and a dependency-free browser interface.

## What it models

The mechanistic simulator tracks four state variables over time: mRNA, protein, nucleotide pool, and amino-acid pool. It uses saturable transcription and translation terms, first-order mRNA/protein loss, explicit substrate depletion, and fourth-order Runge–Kutta integration.

Transcription is represented as:

```text
v_tx = Vmax_tx × DNA/(Kd + DNA) × [NTP/(Km_NTP + NTP)]^4
```

Translation is represented as:

```text
v_tl = (elongation_rate × 60 / protein_length)
       × ribosome
       × mRNA/(Km_mRNA + mRNA)
       × AA/(Km_AA + AA)
```

The nucleotide and amino-acid pools decrease according to transcript and protein synthesis. The model is intended for exploratory parameter studies and teaching. Quantitative prediction requires calibration against a specific cell-free extract, DNA construct, reaction composition, temperature, and measurement system.

## Features

- Deterministic TXTL simulation with RK4 integration
- Explicit NTP and amino-acid depletion
- Configurable DNA, ribosome, kinetic, decay, and construct parameters
- Browser interface with light and dark themes
- CSV export of the simulated time series
- Python CLI for single and batch simulations
- Optional local FastAPI endpoint
- Backward-compatible rule-based `audit` command, clearly separated from the kinetic model

## Browser use

The browser application performs the same reduced equations directly in JavaScript. No input data are uploaded by the application, and no Python runtime or Pyodide download is required.

The interface is designed to fit within a single desktop viewport and uses a compact layout on mobile devices.

## Python use

Requires Python 3.10 or newer.

```bash
python -m pip install -e .
python cli.py simulate
```

Example with explicit parameters:

```bash
python cli.py simulate \
  --dna-nm 5 \
  --ntp-mm 1.5 \
  --aa-mm 2.0 \
  --ribosome-nm 50 \
  --duration-min 120 \
  --protein-length-aa 240 \
  --csv-out txtl_simulation.csv
```

Batch simulation:

```bash
python cli.py batch -i sample.csv -o results.csv
```

The sample CSV uses kinetic parameter columns. Missing optional kinetic columns fall back to the model defaults.

## Optional local API

```bash
python -m pip install -e ".[server]"
python cli.py serve
```

The local API exposes `GET /health` and `POST /api/simulate`. GitHub Pages is static and does not run the FastAPI server.

## Development and testing

```bash
python -m pip install -e ".[dev,server]"
pytest -v
python -m compileall -q txtl_simulator cli.py txtl_simulator_app.py
```

CI tests Python 3.10 through 3.13 and runs both single-simulation and batch smoke tests.

## Privacy

The static browser interface runs locally in the browser and does not transmit entered parameters. The optional FastAPI server runs wherever the user starts it; deployment, access control, logging, and network security are the operator's responsibility.

## Browser compatibility

The static interface targets current versions of Chrome, Edge, Firefox, and Safari with JavaScript enabled.

## License

MIT. See [LICENSE](LICENSE).
