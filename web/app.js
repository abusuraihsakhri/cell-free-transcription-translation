"use strict";

const defaults = {
  dna_nm: 5,
  ntp_mm: 1.5,
  aa_mm: 2,
  ribosome_nm: 50,
  duration_min: 120,
  protein_length_aa: 240,
  vmax_tx_nm_min: 100,
  promoter_kd_nm: 1,
  ntp_km_mm: 0.1,
  mrna_km_nm: 20,
  aa_km_mm: 0.2,
  elongation_aa_s: 10,
  mrna_half_life_min: 8,
  protein_half_life_min: 240,
  nt_per_transcript: 720,
  dt_min: 0.1
};

let lastResult = null;

function numberFrom(id) {
  const element = document.getElementById(id);
  const value = Number(element.value);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(element.closest("label").querySelector("span").textContent.trim() + " must be greater than zero.");
  }
  return value;
}

function readParameters() {
  const params = {};
  Object.keys(defaults).forEach(function (key) {
    params[key] = numberFrom(key);
  });
  if (params.dt_min > params.duration_min) {
    throw new Error("Integration step cannot exceed the simulation duration.");
  }
  if (params.duration_min / params.dt_min > 200000) {
    throw new Error("Choose a larger integration step; the current settings exceed 200,000 steps.");
  }
  return params;
}

function transcriptionRate(ntp, p) {
  const dnaSat = p.dna_nm / (p.promoter_kd_nm + p.dna_nm);
  const ntpSat = ntp / (p.ntp_km_mm + ntp);
  return p.vmax_tx_nm_min * dnaSat * Math.pow(ntpSat, 4);
}

function translationRate(mrna, aa, p) {
  const mrnaSat = mrna > 0 ? mrna / (p.mrna_km_nm + mrna) : 0;
  const aaSat = aa / (p.aa_km_mm + aa);
  const proteinsPerRibosomeMin = p.elongation_aa_s * 60 / p.protein_length_aa;
  return proteinsPerRibosomeMin * p.ribosome_nm * mrnaSat * aaSat;
}

function derivatives(state, p) {
  const mrna = Math.max(0, state[0]);
  const protein = Math.max(0, state[1]);
  const ntp = Math.max(0, state[2]);
  const aa = Math.max(0, state[3]);
  const tx = transcriptionRate(ntp, p);
  const tl = translationRate(mrna, aa, p);
  const mrnaDecay = Math.log(2) / p.mrna_half_life_min;
  const proteinDecay = Math.log(2) / p.protein_half_life_min;

  return [
    tx - mrnaDecay * mrna,
    tl - proteinDecay * protein,
    -(p.nt_per_transcript * tx) / 1000000,
    -(p.protein_length_aa * tl) / 1000000
  ];
}

function combine(state, derivative, scale) {
  return state.map(function (value, index) {
    return value + scale * derivative[index];
  });
}

function rk4Step(state, h, p) {
  const k1 = derivatives(state, p);
  const k2 = derivatives(combine(state, k1, h / 2), p);
  const k3 = derivatives(combine(state, k2, h / 2), p);
  const k4 = derivatives(combine(state, k3, h), p);

  return state.map(function (value, index) {
    const next = value + h * (k1[index] + 2 * k2[index] + 2 * k3[index] + k4[index]) / 6;
    return Math.max(0, next);
  });
}

function runSimulation(p) {
  let state = [0, 0, p.ntp_mm, p.aa_mm];
  let time = 0;
  const points = [];

  while (true) {
    const tx = transcriptionRate(state[2], p);
    const tl = translationRate(state[0], state[3], p);
    points.push({
      time_min: time,
      mrna_nm: state[0],
      protein_nm: state[1],
      ntp_mm: state[2],
      aa_mm: state[3],
      transcription_rate_nm_min: tx,
      translation_rate_nm_min: tl
    });

    if (time >= p.duration_min - 1e-12) {
      break;
    }
    const h = Math.min(p.dt_min, p.duration_min - time);
    state = rk4Step(state, h, p);
    time += h;
  }

  const finalPoint = points[points.length - 1];
  let peakMrna = 0;
  let peakTranslation = 0;
  points.forEach(function (point) {
    peakMrna = Math.max(peakMrna, point.mrna_nm);
    peakTranslation = Math.max(peakTranslation, point.translation_rate_nm_min);
  });

  const ntpFraction = finalPoint.ntp_mm / p.ntp_mm;
  const aaFraction = finalPoint.aa_mm / p.aa_mm;

  return {
    parameters: p,
    points: points,
    summary: {
      final_protein_nm: finalPoint.protein_nm,
      peak_mrna_nm: peakMrna,
      residual_ntp_mm: finalPoint.ntp_mm,
      residual_aa_mm: finalPoint.aa_mm,
      peak_translation_rate_nm_min: peakTranslation,
      ntp_fraction_remaining: ntpFraction,
      aa_fraction_remaining: aaFraction,
      substrate_limited: ntpFraction < 0.1 || aaFraction < 0.1
    }
  };
}

function formatNumber(value) {
  if (!Number.isFinite(value)) return "—";
  if (Math.abs(value) >= 10000) return value.toExponential(2);
  if (Math.abs(value) >= 100) return value.toFixed(1);
  if (Math.abs(value) >= 1) return value.toFixed(2);
  return value.toFixed(3);
}

function updateSummary(result) {
  const s = result.summary;
  document.getElementById("finalProtein").textContent = formatNumber(s.final_protein_nm);
  document.getElementById("peakMrna").textContent = formatNumber(s.peak_mrna_nm);
  document.getElementById("ntpRemaining").textContent = formatNumber(s.residual_ntp_mm);
  document.getElementById("aaRemaining").textContent = formatNumber(s.residual_aa_mm);

  const badge = document.getElementById("limitBadge");
  const interpretation = document.getElementById("interpretation");

  if (s.substrate_limited) {
    badge.textContent = "Substrate limited";
    interpretation.textContent =
      "At least one substrate pool falls below 10% of its initial concentration. The late-phase trajectory is therefore strongly resource-limited in this reduced model.";
  } else {
    badge.textContent = "Resources retained";
    interpretation.textContent =
      "Both modeled substrate pools remain above 10% of baseline over the selected duration. Compare parameter sweeps rather than treating the absolute yield as experimentally calibrated.";
  }
}

function cssColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function drawPlot(result) {
  const canvas = document.getElementById("plot");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(240, Math.floor(rect.width));
  const height = Math.max(90, Math.floor(rect.height));
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);

  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);

  const pad = { left: 34, right: 10, top: 10, bottom: 23 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const points = result.points;
  const maxTime = result.parameters.duration_min || 1;
  const maxProtein = Math.max.apply(null, points.map(function (p) { return p.protein_nm; })) || 1;
  const maxMrna = Math.max.apply(null, points.map(function (p) { return p.mrna_nm; })) || 1;
  const border = cssColor("--border");
  const muted = cssColor("--muted");

  ctx.strokeStyle = border;
  ctx.lineWidth = 1;
  ctx.fillStyle = muted;
  ctx.font = "10px system-ui, sans-serif";
  ctx.textAlign = "center";

  for (let i = 0; i <= 4; i += 1) {
    const y = pad.top + plotH * i / 4;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
  }

  ctx.textAlign = "right";
  ctx.fillText("100%", pad.left - 5, pad.top + 3);
  ctx.fillText("0%", pad.left - 5, pad.top + plotH + 3);
  ctx.textAlign = "center";
  ctx.fillText("0", pad.left, height - 6);
  ctx.fillText(formatNumber(maxTime) + " min", width - pad.right - 8, height - 6);

  function drawSeries(accessor, maximum, color) {
    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    let started = false;
    const stride = Math.max(1, Math.floor(points.length / Math.max(200, width)));

    for (let i = 0; i < points.length; i += stride) {
      const point = points[i];
      const x = pad.left + (point.time_min / maxTime) * plotW;
      const y = pad.top + plotH - (accessor(point) / maximum) * plotH;
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }

    const last = points[points.length - 1];
    ctx.lineTo(
      pad.left + (last.time_min / maxTime) * plotW,
      pad.top + plotH - (accessor(last) / maximum) * plotH
    );
    ctx.stroke();
  }

  drawSeries(function (p) { return p.protein_nm; }, maxProtein, cssColor("--protein"));
  drawSeries(function (p) { return p.mrna_nm; }, maxMrna, cssColor("--mrna"));
}

function runAndRender() {
  const error = document.getElementById("errorMessage");
  error.textContent = "";

  try {
    const params = readParameters();
    lastResult = runSimulation(params);
    updateSummary(lastResult);
    drawPlot(lastResult);
    document.getElementById("downloadButton").disabled = false;
  } catch (err) {
    lastResult = null;
    document.getElementById("downloadButton").disabled = true;
    error.textContent = err instanceof Error ? err.message : String(err);
  }
}

function resetForm() {
  Object.keys(defaults).forEach(function (key) {
    document.getElementById(key).value = defaults[key];
  });
  runAndRender();
}

function csvEscape(value) {
  const text = String(value);
  if (/[",\n]/.test(text)) {
    return '"' + text.replace(/"/g, '""') + '"';
  }
  return text;
}

function downloadCsv() {
  if (!lastResult) return;
  const columns = [
    "time_min",
    "mrna_nm",
    "protein_nm",
    "ntp_mm",
    "aa_mm",
    "transcription_rate_nm_min",
    "translation_rate_nm_min"
  ];
  const rows = [columns.join(",")];

  lastResult.points.forEach(function (point) {
    rows.push(columns.map(function (column) {
      return csvEscape(point[column]);
    }).join(","));
  });

  const blob = new Blob([rows.join("\n") + "\n"], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "txtl_simulation.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("txtl-theme", theme);
  if (lastResult) {
    requestAnimationFrame(function () { drawPlot(lastResult); });
  }
}

function initializeTheme() {
  const saved = localStorage.getItem("txtl-theme");
  const preferred = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(saved || (preferred ? "dark" : "light"));
}

document.getElementById("modelForm").addEventListener("submit", function (event) {
  event.preventDefault();
  runAndRender();
});

document.getElementById("resetButton").addEventListener("click", resetForm);
document.getElementById("downloadButton").addEventListener("click", downloadCsv);
document.getElementById("themeToggle").addEventListener("click", function () {
  const current = document.documentElement.dataset.theme || "light";
  applyTheme(current === "dark" ? "light" : "dark");
});

if ("ResizeObserver" in window) {
  new ResizeObserver(function () {
    if (lastResult) drawPlot(lastResult);
  }).observe(document.getElementById("plot"));
} else {
  window.addEventListener("resize", function () {
    if (lastResult) drawPlot(lastResult);
  });
}

initializeTheme();
runAndRender();
