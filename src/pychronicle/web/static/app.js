/**
 * PyChronicle Interactive Time-Travel Debugger — Frontend Application
 */

(function () {
  "use strict";

  // Application State
  const state = {
    databases: [],
    activeDb: "",
    runs: [],
    activeRun: null,
    events: [],
    currentEventIndex: 0,
    sourceCode: "",
    sourceLines: [],
    astData: null,
    snapshotCache: new Map(), // event_id -> snapshot
    watchlist: new Set(["total", "subtotal", "grand_total", "x", "y"]),
    isPlaying: false,
    playInterval: null,
    playSpeed: 600,
    selectedVar: null,
    lineHeatCounts: new Map(), // line -> execution count
    showHeatmap: true,
    filterVars: "",
    filterAST: "",
    filterEvents: "",
    activeTab: "vars",
    examples: [],
  };

  // DOM Elements Cache
  const el = {
    dbSelect: document.getElementById("db-select"),
    runSelect: document.getElementById("run-select"),
    sumTarget: document.getElementById("sum-target"),
    sumStatus: document.getElementById("sum-status"),
    sumEvents: document.getElementById("sum-events"),
    sumDuration: document.getElementById("sum-duration"),
    sumFrame: document.getElementById("sum-frame"),

    btnStepFirst: document.getElementById("btn-step-first"),
    btnStepBack: document.getElementById("btn-step-backward"),
    btnPlayPause: document.getElementById("btn-play-pause"),
    btnStepForward: document.getElementById("btn-step-forward"),
    btnStepLast: document.getElementById("btn-step-last"),
    timelineSlider: document.getElementById("timeline-slider"),
    scrubberFill: document.getElementById("scrubber-fill"),
    stepCurr: document.getElementById("step-curr"),
    stepTotal: document.getElementById("step-total"),
    ctxFunction: document.getElementById("ctx-function"),
    ctxLine: document.getElementById("ctx-line"),
    eventPct: document.getElementById("event-pct"),
    speedSelect: document.getElementById("speed-select"),

    codeFileName: document.getElementById("code-file-name"),
    codeLineCount: document.getElementById("code-line-count"),
    codeContainer: document.getElementById("code-container"),
    codeViewport: document.getElementById("code-viewport"),
    toggleHeatmap: document.getElementById("toggle-heatmap"),
    footerActiveIndicator: document.getElementById("footer-active-indicator"),

    deltaCallout: document.getElementById("delta-callout"),
    deltaTags: document.getElementById("delta-tags"),
    watchInput: document.getElementById("watch-input"),
    btnAddWatch: document.getElementById("btn-add-watch"),
    watchChips: document.getElementById("watch-chips"),
    watchCount: document.getElementById("watch-count"),
    filterVarsInput: document.getElementById("filter-vars-input"),
    variablesTbody: document.getElementById("variables-tbody"),
    inspectorTargetName: document.getElementById("inspector-target-name"),
    inspectorContent: document.getElementById("inspector-content"),

    astTotalAssignments: document.getElementById("ast-total-assignments"),
    astUniqueVars: document.getElementById("ast-unique-vars"),
    astTotalScopes: document.getElementById("ast-total-scopes"),
    kindPills: document.getElementById("kind-pills"),
    astFilterInput: document.getElementById("ast-filter-input"),
    astTbody: document.getElementById("ast-tbody"),

    stackFramesList: document.getElementById("stack-frames-list"),
    eventsFilterInput: document.getElementById("events-filter-input"),
    eventsTbody: document.getElementById("events-tbody"),

    // Modals
    modalTrace: document.getElementById("modal-trace"),
    modalShortcuts: document.getElementById("modal-shortcuts"),
    btnOpenTraceModal: document.getElementById("btn-open-trace-modal"),
    btnCloseModalTrace: document.getElementById("btn-close-modal-trace"),
    btnCancelTrace: document.getElementById("btn-cancel-trace"),
    btnRunTrace: document.getElementById("btn-run-trace"),
    btnShortcutsModal: document.getElementById("btn-shortcuts-modal"),
    btnCloseModalShortcuts: document.getElementById("btn-close-modal-shortcuts"),
    btnExportJson: document.getElementById("btn-export-json"),

    examplePicker: document.getElementById("example-picker"),
    traceTargetDb: document.getElementById("trace-target-db"),
    traceCodeInput: document.getElementById("trace-code-input"),
    editorCharCount: document.getElementById("editor-char-count"),
    toastContainer: document.getElementById("toast-container"),
  };

  // ==========================================================================
  // Initialization & Network Fetching
  // ==========================================================================

  async function init() {
    setupEventListeners();
    await loadDatabases();
    await loadExamples();
  }

  async function loadDatabases() {
    try {
      const res = await fetch("/api/databases");
      if (!res.ok) throw new Error("Failed to fetch databases");
      const data = await res.json();
      state.databases = data.databases || [];
      state.activeDb = data.active || (state.databases.length ? state.databases[0] : "history.sqlite3");

      el.dbSelect.innerHTML = "";
      if (state.databases.length === 0) {
        el.dbSelect.innerHTML = '<option value="history.sqlite3">history.sqlite3 (new)</option>';
      } else {
        state.databases.forEach((db) => {
          const opt = document.createElement("option");
          opt.value = db;
          opt.textContent = db;
          if (db === state.activeDb) opt.selected = true;
          el.dbSelect.appendChild(opt);
        });
      }

      await loadRuns();
    } catch (err) {
      showToast("Cannot connect to PyChronicle backend: " + err.message, "error");
    }
  }

  async function loadRuns() {
    try {
      const res = await fetch("/api/runs");
      if (!res.ok) throw new Error("Failed to fetch runs");
      state.runs = await res.json();

      el.runSelect.innerHTML = "";
      if (state.runs.length === 0) {
        el.runSelect.innerHTML = '<option value="">No recorded runs found</option>';
        clearWorkspace();
        return;
      }

      state.runs.forEach((run, idx) => {
        const opt = document.createElement("option");
        opt.value = run.id;
        const timeStr = new Date(run.started_at * 1000).toLocaleTimeString();
        opt.textContent = `Run #${run.id}: ${run.target_name} (${run.event_count} events, ${timeStr})`;
        el.runSelect.appendChild(opt);
      });

      // Default to latest run (first in list)
      const selectedRun = state.runs[0];
      state.activeRun = selectedRun;
      el.runSelect.value = selectedRun.id;

      await loadRunDetails(selectedRun);
    } catch (err) {
      showToast("Error loading runs: " + err.message, "error");
    }
  }

  async function loadRunDetails(run) {
    if (!run) return;
    state.activeRun = run;

    // Update Summary Header
    el.sumTarget.textContent = run.target_name || run.target;
    el.sumTarget.title = run.target;
    el.sumStatus.textContent = run.status;
    el.sumStatus.className = `status-pill status-${run.status === "completed" ? "completed" : "failed"}`;
    el.sumEvents.textContent = run.event_count;

    if (run.finished_at && run.started_at) {
      const dur = Math.max(0, run.finished_at - run.started_at);
      el.sumDuration.textContent = `${dur.toFixed(2)}s`;
    } else {
      el.sumDuration.textContent = "-";
    }

    // Load Timeline Events
    await loadTimeline(run.id);

    // Load Source Code & AST
    await loadSource(run.target);
    await loadAST(run.target);
  }

  async function loadTimeline(runId) {
    try {
      const res = await fetch(`/api/timeline?run_id=${runId}`);
      if (!res.ok) throw new Error("Failed to fetch timeline");
      state.events = await res.json();
      state.snapshotCache.clear();

      // Compute heatmap frequencies
      state.lineHeatCounts.clear();
      state.events.forEach((ev) => {
        const count = state.lineHeatCounts.get(ev.line_number) || 0;
        state.lineHeatCounts.set(ev.line_number, count + 1);
      });

      const total = state.events.length;
      el.stepTotal.textContent = total;
      el.timelineSlider.max = Math.max(0, total - 1);

      if (total > 0) {
        state.currentEventIndex = 0;
        await stepTo(0);
      } else {
        el.stepCurr.textContent = 0;
        el.eventPct.textContent = "0%";
      }

      renderEventsLog();
    } catch (err) {
      showToast("Error loading timeline: " + err.message, "error");
    }
  }

  async function loadSource(targetPath) {
    try {
      const res = await fetch(`/api/source?path=${encodeURIComponent(targetPath)}`);
      if (!res.ok) throw new Error("Could not load source file");
      const data = await res.json();
      state.sourceCode = data.content;
      state.sourceLines = data.lines;

      el.codeFileName.textContent = data.filename;
      el.codeFileName.title = data.path;
      el.codeLineCount.textContent = `${data.line_count} lines`;

      renderCode();
    } catch (err) {
      el.codeContainer.innerHTML = `<div class="code-placeholder"><p style="color: #f43f5e;">Cannot read source file: ${err.message}</p></div>`;
    }
  }

  async function loadAST(targetPath) {
    try {
      const res = await fetch(`/api/ast?path=${encodeURIComponent(targetPath)}`);
      if (!res.ok) throw new Error("AST analysis error");
      state.astData = await res.json();
      renderAST();
    } catch (err) {
      console.warn("AST fetch error:", err);
    }
  }

  async function loadExamples() {
    try {
      const res = await fetch("/api/examples");
      if (!res.ok) return;
      state.examples = await res.json();

      el.examplePicker.innerHTML = '<option value="">-- Choose Example --</option>';
      state.examples.forEach((ex) => {
        const opt = document.createElement("option");
        opt.value = ex.name;
        opt.textContent = `${ex.name} (${ex.size} bytes)`;
        el.examplePicker.appendChild(opt);
      });
    } catch (err) {
      console.warn("Could not load examples:", err);
    }
  }

  // ==========================================================================
  // Timeline Navigation & Stepping
  // ==========================================================================

  async function stepTo(index) {
    if (!state.events || state.events.length === 0) return;
    index = Math.max(0, Math.min(state.events.length - 1, index));
    state.currentEventIndex = index;

    const event = state.events[index];
    const total = state.events.length;

    // Update Scrubber Controls
    el.timelineSlider.value = index;
    el.stepCurr.textContent = index + 1;
    const pct = total > 1 ? Math.round((index / (total - 1)) * 100) : 100;
    el.scrubberFill.style.width = `${pct}%`;
    el.eventPct.textContent = `${pct}%`;

    el.ctxFunction.textContent = event.function_name;
    el.ctxLine.textContent = `line ${event.line_number}`;
    el.sumFrame.textContent = `frame #${event.frame_id}`;

    // Highlight Code Viewer Line
    highlightActiveCodeLine(event.line_number, event);

    // Fetch snapshot variables
    let snapshot = state.snapshotCache.get(event.id);
    if (!snapshot) {
      try {
        const res = await fetch(`/api/snapshot?event_id=${event.id}&frame_id=${event.frame_id}`);
        if (res.ok) {
          snapshot = await res.json();
          state.snapshotCache.set(event.id, snapshot);
        }
      } catch (err) {
        console.warn("Snapshot fetch error:", err);
      }
    }

    const variables = snapshot ? snapshot.variables : {};

    // Render Inspector Panels
    renderDeltaCallout(event.changes);
    renderVariables(variables, event.changes);
    renderWatchlist(variables);
    renderCallStack(event);
    updateEventsLogActiveRow(index);

    el.footerActiveIndicator.textContent = `Seq #${event.sequence} • ${event.function_name}() • L${event.line_number}`;
  }

  function stepNext() {
    if (state.currentEventIndex < state.events.length - 1) {
      stepTo(state.currentEventIndex + 1);
    } else if (state.isPlaying) {
      pause();
    }
  }

  function stepPrev() {
    if (state.currentEventIndex > 0) {
      stepTo(state.currentEventIndex - 1);
    }
  }

  function stepFirst() {
    stepTo(0);
  }

  function stepLast() {
    if (state.events.length > 0) {
      stepTo(state.events.length - 1);
    }
  }

  function togglePlay() {
    if (state.isPlaying) {
      pause();
    } else {
      play();
    }
  }

  function play() {
    if (state.events.length === 0) return;
    if (state.currentEventIndex >= state.events.length - 1) {
      state.currentEventIndex = 0;
    }
    state.isPlaying = true;
    el.btnPlayPause.querySelector(".icon-play").classList.add("hide");
    el.btnPlayPause.querySelector(".icon-pause").classList.remove("hide");

    clearInterval(state.playInterval);
    state.playInterval = setInterval(() => {
      stepNext();
    }, state.playSpeed);
  }

  function pause() {
    state.isPlaying = false;
    clearInterval(state.playInterval);
    el.btnPlayPause.querySelector(".icon-play").classList.remove("hide");
    el.btnPlayPause.querySelector(".icon-pause").classList.add("hide");
  }

  // ==========================================================================
  // Code Viewer & Syntax Highlighting
  // ==========================================================================

  function renderCode() {
    el.codeContainer.innerHTML = "";
    if (!state.sourceLines || state.sourceLines.length === 0) {
      el.codeContainer.innerHTML = '<div class="code-placeholder"><p>No code available.</p></div>';
      return;
    }

    const maxHeat = Math.max(1, ...Array.from(state.lineHeatCounts.values()));

    const fragment = document.createDocumentFragment();
    state.sourceLines.forEach((rawText, idx) => {
      const lineNum = idx + 1;
      const lineDiv = document.createElement("div");
      lineDiv.className = "code-line";
      lineDiv.id = `code-line-${lineNum}`;
      lineDiv.dataset.line = lineNum;

      // Indicator Arrow Slot
      const indDiv = document.createElement("div");
      indDiv.className = "line-indicator";
      indDiv.innerHTML = '<span class="line-indicator-arrow hide">►</span>';

      // Line Number
      const numDiv = document.createElement("div");
      numDiv.className = "line-number";
      numDiv.textContent = lineNum;

      // Execution Heat Bar
      const heatDiv = document.createElement("div");
      heatDiv.className = "line-heat-bar";
      const heatCount = state.lineHeatCounts.get(lineNum) || 0;
      if (heatCount > 0 && state.showHeatmap) {
        const ratio = heatCount / maxHeat;
        const alpha = Math.min(1, 0.25 + ratio * 0.75);
        heatDiv.style.background = `rgba(6, 182, 212, ${alpha})`;
        heatDiv.title = `Executed ${heatCount} time(s)`;
      }

      // Syntax-highlighted line text
      const textDiv = document.createElement("div");
      textDiv.className = "line-text";
      textDiv.innerHTML = highlightPythonLine(rawText);

      lineDiv.appendChild(indDiv);
      lineDiv.appendChild(numDiv);
      lineDiv.appendChild(heatDiv);
      lineDiv.appendChild(textDiv);

      fragment.appendChild(lineDiv);
    });

    el.codeContainer.appendChild(fragment);
  }

  function highlightActiveCodeLine(activeLineNum, event) {
    // Remove previous active classes
    const prevActive = el.codeContainer.querySelectorAll(".code-line.active");
    prevActive.forEach((row) => {
      row.classList.remove("active");
      const arrow = row.querySelector(".line-indicator-arrow");
      if (arrow) arrow.classList.add("hide");
      const badge = row.querySelector(".line-delta-badge");
      if (badge) badge.remove();
    });

    const targetRow = document.getElementById(`code-line-${activeLineNum}`);
    if (targetRow) {
      targetRow.classList.add("active");
      const arrow = targetRow.querySelector(".line-indicator-arrow");
      if (arrow) arrow.classList.remove("hide");

      // Add inline delta badges if variables modified
      if (event && event.changes && Object.keys(event.changes).length > 0) {
        const changedNames = Object.keys(event.changes).join(", ");
        const badge = document.createElement("span");
        badge.className = "line-delta-badge";
        badge.textContent = `Δ ${changedNames}`;
        targetRow.appendChild(badge);
      }

      // Scroll into view gently
      targetRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function highlightPythonLine(line) {
    if (!line) return "&nbsp;";

    // Escape basic HTML chars
    let s = line
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Match comments
    const commentMatch = s.match(/(#.*$)/);
    let comment = "";
    if (commentMatch) {
      comment = `<span class="py-comment">${commentMatch[1]}</span>`;
      s = s.slice(0, commentMatch.index);
    }

    // Match strings ("..." or '...')
    s = s.replace(/(".*?"|'.*?'|""".*?"""|'''.*?''')/g, '<span class="py-string">$1</span>');

    // Match numbers
    s = s.replace(/\b(\d+(\.\d+)?)\b/g, '<span class="py-number">$1</span>');

    // Match keywords
    const keywords = [
      "def", "class", "return", "if", "elif", "else", "for", "while", "in", "import",
      "from", "as", "try", "except", "finally", "raise", "with", "yield", "pass",
      "break", "continue", "lambda", "global", "nonlocal", "async", "await"
    ];
    const kwRegex = new RegExp(`\\b(${keywords.join("|")})\\b`, "g");
    s = s.replace(kwRegex, '<span class="py-keyword">$1</span>');

    // Match built-in booleans and values
    s = s.replace(/\b(True|False|None)\b/g, '<span class="py-builtin">$1</span>');

    // Match function defs
    s = s.replace(/(def\s+)([a-zA-Z_]\w*)/g, '$1<span class="py-func">$2</span>');

    // Match class defs
    s = s.replace(/(class\s+)([a-zA-Z_]\w*)/g, '$1<span class="py-class">$2</span>');

    // Reattach comment
    return s + comment;
  }

  // ==========================================================================
  // Inspector: Variables, Mutations & Watchlist
  // ==========================================================================

  function renderDeltaCallout(changes) {
    el.deltaTags.innerHTML = "";
    if (!changes || Object.keys(changes).length === 0) {
      el.deltaTags.innerHTML = '<span class="empty-hint">No variables mutated at this line transition.</span>';
      return;
    }

    Object.entries(changes).forEach(([name, val]) => {
      const pill = document.createElement("div");
      pill.className = "delta-pill";
      const displayVal = formatDisplayValue(val);
      pill.innerHTML = `<span class="var-name">${name}</span> <span class="var-op">=</span> <span class="var-val">${escapeHtml(displayVal)}</span>`;
      pill.onclick = () => inspectObject(name, val);
      el.deltaTags.appendChild(pill);
    });
  }

  function renderVariables(variables, currentChanges) {
    el.variablesTbody.innerHTML = "";
    const filter = state.filterVars.trim().toLowerCase();

    const keys = Object.keys(variables || {}).sort((a, b) => {
      // Pinned items first
      const aWatch = state.watchlist.has(a);
      const bWatch = state.watchlist.has(b);
      if (aWatch && !bWatch) return -1;
      if (!aWatch && bWatch) return 1;

      // Dunder variables (__doc__, __builtins__) pushed to bottom
      const aDunder = a.startsWith("__") && a.endsWith("__");
      const bDunder = b.startsWith("__") && b.endsWith("__");
      if (!aDunder && bDunder) return -1;
      if (aDunder && !bDunder) return 1;

      return a.localeCompare(b);
    });

    const filteredKeys = keys.filter((k) => !filter || k.toLowerCase().includes(filter));

    if (filteredKeys.length === 0) {
      el.variablesTbody.innerHTML = '<tr><td colspan="4" class="empty-state">No matching variables found.</td></tr>';
      return;
    }

    const fragment = document.createDocumentFragment();
    filteredKeys.forEach((key) => {
      const val = variables[key];
      const isWatched = state.watchlist.has(key);
      const isJustChanged = currentChanges && key in currentChanges;
      const valType = inferType(val);
      const displayVal = formatDisplayValue(val);

      const tr = document.createElement("tr");
      if (isJustChanged) tr.style.background = "rgba(139, 92, 246, 0.15)";
      if (state.selectedVar === key) tr.classList.add("selected");

      // Star cell
      const tdWatch = document.createElement("td");
      tdWatch.className = "col-watch";
      tdWatch.innerHTML = isWatched ? "★" : "☆";
      tdWatch.style.color = isWatched ? "#fbbf24" : "#64748b";
      tdWatch.style.cursor = "pointer";
      tdWatch.onclick = (e) => {
        e.stopPropagation();
        toggleWatch(key);
        renderVariables(variables, currentChanges);
      };

      // Name cell
      const tdName = document.createElement("td");
      tdName.className = "col-name";
      tdName.textContent = key;
      if (isJustChanged) {
        tdName.innerHTML = `${key} <span style="font-size: 10px; color: #a78bfa;">(Δ)</span>`;
      }

      // Type cell
      const tdType = document.createElement("td");
      tdType.innerHTML = `<span class="type-pill type-${valType}">${valType}</span>`;

      // Value cell
      const tdVal = document.createElement("td");
      tdVal.className = "col-value";
      tdVal.textContent = displayVal;

      tr.appendChild(tdWatch);
      tr.appendChild(tdName);
      tr.appendChild(tdType);
      tr.appendChild(tdVal);

      tr.onclick = () => {
        state.selectedVar = key;
        inspectObject(key, val);
        el.variablesTbody.querySelectorAll("tr").forEach((r) => r.classList.remove("selected"));
        tr.classList.add("selected");
      };

      fragment.appendChild(tr);
    });

    el.variablesTbody.appendChild(fragment);
  }

  function renderWatchlist(variables) {
    el.watchChips.innerHTML = "";
    el.watchCount.textContent = state.watchlist.size;

    if (state.watchlist.size === 0) {
      el.watchChips.innerHTML = '<span class="empty-hint">No variables pinned yet.</span>';
      return;
    }

    state.watchlist.forEach((name) => {
      const chip = document.createElement("div");
      chip.className = "watch-chip";
      const val = variables ? variables[name] : undefined;
      const valStr = val !== undefined ? formatDisplayValue(val) : "undefined";

      chip.innerHTML = `<span><strong>${name}</strong>: ${escapeHtml(valStr)}</span>`;
      const btnRem = document.createElement("button");
      btnRem.className = "btn-remove-chip";
      btnRem.innerHTML = "&times;";
      btnRem.title = "Unpin variable";
      btnRem.onclick = () => {
        state.watchlist.delete(name);
        renderWatchlist(variables);
        renderVariables(variables, null);
      };
      chip.appendChild(btnRem);
      el.watchChips.appendChild(chip);
    });
  }

  function toggleWatch(name) {
    if (state.watchlist.has(name)) {
      state.watchlist.delete(name);
    } else {
      state.watchlist.add(name);
    }
    renderWatchlist(getLatestSnapshotVariables());
  }

  function inspectObject(name, value) {
    el.inspectorTargetName.textContent = name;
    try {
      el.inspectorContent.textContent = JSON.stringify(value, null, 2);
    } catch {
      el.inspectorContent.textContent = String(value);
    }
  }

  // ==========================================================================
  // Inspector: AST Static Analysis
  // ==========================================================================

  function renderAST() {
    if (!state.astData) return;

    el.astTotalAssignments.textContent = state.astData.assignments.length;
    el.astUniqueVars.textContent = state.astData.all_variables.length;
    el.astTotalScopes.textContent = Object.keys(state.astData.scopes || {}).length;

    // Render Grammar Kind Pills
    el.kindPills.innerHTML = "";
    const kindCounts = {};
    state.astData.assignments.forEach((a) => {
      kindCounts[a.kind] = (kindCounts[a.kind] || 0) + 1;
    });

    Object.entries(kindCounts).forEach(([kind, count]) => {
      const pill = document.createElement("span");
      pill.className = "kind-badge";
      pill.textContent = `${kind}: ${count}`;
      el.kindPills.appendChild(pill);
    });

    // Render Assignments Table
    renderASTTable();
  }

  function renderASTTable() {
    el.astTbody.innerHTML = "";
    if (!state.astData || state.astData.assignments.length === 0) {
      el.astTbody.innerHTML = '<tr><td colspan="6" class="empty-state">No assignments detected.</td></tr>';
      return;
    }

    const filter = state.filterAST.trim().toLowerCase();
    const filtered = state.astData.assignments.filter((a) => {
      if (!filter) return true;
      return (
        a.target_name.toLowerCase().includes(filter) ||
        a.kind.toLowerCase().includes(filter) ||
        a.scope_name.toLowerCase().includes(filter)
      );
    });

    if (filtered.length === 0) {
      el.astTbody.innerHTML = '<tr><td colspan="6" class="empty-state">No matching assignments.</td></tr>';
      return;
    }

    const fragment = document.createDocumentFragment();
    filtered.forEach((rec) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="color: #fbbf24; font-weight: 600;">L${rec.line_number}</td>
        <td style="color: #38bdf8; font-weight: 600;">${escapeHtml(rec.target_name)}</td>
        <td><span class="kind-badge">${rec.kind}</span></td>
        <td style="color: #c084fc;">${escapeHtml(rec.scope_name)}</td>
        <td>${rec.is_definition ? '<span style="color: #34d399; font-weight: 700;">YES</span>' : '<span style="color: #64748b;">NO</span>'}</td>
        <td style="color: #94a3b8; font-style: italic;">${escapeHtml(rec.raw_code_snippet || "-")}</td>
      `;

      tr.onclick = () => {
        // Jump to code line
        const targetRow = document.getElementById(`code-line-${rec.line_number}`);
        if (targetRow) {
          targetRow.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      };

      fragment.appendChild(tr);
    });

    el.astTbody.appendChild(fragment);
  }

  // ==========================================================================
  // Inspector: Call Stack & Execution Log
  // ==========================================================================

  function renderCallStack(event) {
    el.stackFramesList.innerHTML = "";
    if (!event) return;

    // Construct stack card
    const card = document.createElement("div");
    card.className = "stack-frame-card active-frame";
    card.innerHTML = `
      <div class="frame-info">
        <span class="frame-id">Frame #${event.frame_id}</span>
        <span class="frame-func">${event.function_name}()</span>
      </div>
      <div class="frame-line">line ${event.line_number}</div>
    `;
    el.stackFramesList.appendChild(card);

    if (event.frame_id > 1) {
      const moduleCard = document.createElement("div");
      moduleCard.className = "stack-frame-card";
      moduleCard.innerHTML = `
        <div class="frame-info">
          <span class="frame-id">Frame #1</span>
          <span class="frame-func">&lt;module&gt;</span>
        </div>
        <div class="frame-line">caller</div>
      `;
      el.stackFramesList.appendChild(moduleCard);
    }
  }

  function renderEventsLog() {
    el.eventsTbody.innerHTML = "";
    const filter = state.filterEvents.trim().toLowerCase();

    const filtered = state.events.filter((e) => {
      if (!filter) return true;
      return (
        e.function_name.toLowerCase().includes(filter) ||
        String(e.line_number).includes(filter) ||
        Object.keys(e.changes).some((k) => k.toLowerCase().includes(filter))
      );
    });

    const fragment = document.createDocumentFragment();
    filtered.forEach((ev, idx) => {
      const tr = document.createElement("tr");
      tr.id = `event-log-row-${ev.sequence}`;
      const changeKeys = Object.keys(ev.changes);
      const changesText = changeKeys.length > 0 ? changeKeys.join(", ") : "-";

      tr.innerHTML = `
        <td style="color: #64748b;">${ev.sequence}</td>
        <td style="color: #fbbf24; font-weight: 600;">L${ev.line_number}</td>
        <td style="color: #a78bfa;">${ev.function_name}</td>
        <td style="color: #38bdf8;">#${ev.frame_id}</td>
        <td style="color: ${changeKeys.length > 0 ? '#34d399' : '#64748b'};">${escapeHtml(changesText)}</td>
      `;

      tr.onclick = () => {
        const evIndex = state.events.findIndex((item) => item.id === ev.id);
        if (evIndex !== -1) stepTo(evIndex);
      };

      fragment.appendChild(tr);
    });

    el.eventsTbody.appendChild(fragment);
  }

  function updateEventsLogActiveRow(activeIdx) {
    if (!state.events[activeIdx]) return;
    const activeSeq = state.events[activeIdx].sequence;
    el.eventsTbody.querySelectorAll("tr").forEach((r) => r.classList.remove("selected"));
    const activeRow = document.getElementById(`event-log-row-${activeSeq}`);
    if (activeRow) {
      activeRow.classList.add("selected");
    }
  }

  // ==========================================================================
  // Event Listeners & Modals
  // ==========================================================================

  function setupEventListeners() {
    // Database and Run Selectors
    el.dbSelect.addEventListener("change", async (e) => {
      const selectedDb = e.target.value;
      if (!selectedDb) return;
      try {
        const res = await fetch("/api/select_db", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ database: selectedDb }),
        });
        if (res.ok) {
          state.activeDb = selectedDb;
          await loadRuns();
          showToast(`Switched active database to ${selectedDb}`, "success");
        }
      } catch (err) {
        showToast("Failed to switch database: " + err.message, "error");
      }
    });

    el.runSelect.addEventListener("change", (e) => {
      const runId = parseInt(e.target.value, 10);
      const run = state.runs.find((r) => r.id === runId);
      if (run) loadRunDetails(run);
    });

    // Playback Buttons
    el.btnStepFirst.addEventListener("click", stepFirst);
    el.btnStepBack.addEventListener("click", stepPrev);
    el.btnPlayPause.addEventListener("click", togglePlay);
    el.btnStepForward.addEventListener("click", stepNext);
    el.btnStepLast.addEventListener("click", stepLast);

    el.timelineSlider.addEventListener("input", (e) => {
      stepTo(parseInt(e.target.value, 10));
    });

    el.speedSelect.addEventListener("change", (e) => {
      state.playSpeed = parseInt(e.target.value, 10);
      if (state.isPlaying) {
        pause();
        play();
      }
    });

    // Code Options
    el.toggleHeatmap.addEventListener("change", (e) => {
      state.showHeatmap = e.target.checked;
      renderCode();
      if (state.events.length > 0) {
        highlightActiveCodeLine(state.events[state.currentEventIndex].line_number, state.events[state.currentEventIndex]);
      }
    });

    // Watchlist Controls
    el.btnAddWatch.addEventListener("click", () => {
      const name = el.watchInput.value.trim();
      if (name) {
        state.watchlist.add(name);
        el.watchInput.value = "";
        renderWatchlist(getLatestSnapshotVariables());
        renderVariables(getLatestSnapshotVariables(), null);
      }
    });

    el.watchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") el.btnAddWatch.click();
    });

    el.filterVarsInput.addEventListener("input", (e) => {
      state.filterVars = e.target.value;
      renderVariables(getLatestSnapshotVariables(), null);
    });

    el.astFilterInput.addEventListener("input", (e) => {
      state.filterAST = e.target.value;
      renderASTTable();
    });

    el.eventsFilterInput.addEventListener("input", (e) => {
      state.filterEvents = e.target.value;
      renderEventsLog();
    });

    // Inspector Tabs
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

        btn.classList.add("active");
        const targetId = btn.getAttribute("aria-controls");
        const targetContent = document.getElementById(targetId);
        if (targetContent) targetContent.classList.add("active");
      });
    });

    // Modals
    el.btnOpenTraceModal.addEventListener("click", () => {
      el.modalTrace.setAttribute("open", "");
    });
    el.btnCloseModalTrace.addEventListener("click", () => el.modalTrace.removeAttribute("open"));
    el.btnCancelTrace.addEventListener("click", () => el.modalTrace.removeAttribute("open"));

    el.btnShortcutsModal.addEventListener("click", () => el.modalShortcuts.setAttribute("open", ""));
    el.btnCloseModalShortcuts.addEventListener("click", () => el.modalShortcuts.removeAttribute("open"));

    // Template Picker inside Trace Modal
    el.examplePicker.addEventListener("change", async (e) => {
      const name = e.target.value;
      if (!name) return;
      try {
        const res = await fetch(`/api/example?name=${encodeURIComponent(name)}`);
        if (res.ok) {
          const data = await res.json();
          el.traceCodeInput.value = data.content;
          el.editorCharCount.textContent = `${data.content.length} chars`;
        }
      } catch (err) {
        showToast("Failed to load example: " + err.message, "error");
      }
    });

    el.traceCodeInput.addEventListener("input", () => {
      el.editorCharCount.textContent = `${el.traceCodeInput.value.length} chars`;
    });

    // Run Trace from Modal
    el.btnRunTrace.addEventListener("click", async () => {
      const code = el.traceCodeInput.value.trim();
      if (!code) {
        showToast("Please enter Python code to trace", "error");
        return;
      }

      el.btnRunTrace.disabled = true;
      el.btnRunTrace.innerHTML = "<span>Tracing in Engine...</span>";

      try {
        const res = await fetch("/api/trace", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code: code }),
        });

        const data = await res.json();
        if (!res.ok || data.error) {
          throw new Error(data.error || "Trace execution failed");
        }

        showToast("Trace completed! Loading into timeline...", "success");
        el.modalTrace.removeAttribute("open");
        await loadDatabases();
      } catch (err) {
        showToast("Execution error: " + err.message, "error");
      } finally {
        el.btnRunTrace.disabled = false;
        el.btnRunTrace.innerHTML = `
          <svg viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
          <span>Run &amp; Time-Travel Debug</span>
        `;
      }
    });

    // Export Trace JSON
    el.btnExportJson.addEventListener("click", () => {
      if (!state.events || state.events.length === 0) {
        showToast("No trace events to export", "error");
        return;
      }
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(
        JSON.stringify({
          run: state.activeRun,
          events: state.events,
          ast: state.astData,
        }, null, 2)
      );
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `pychronicle_run_${state.activeRun ? state.activeRun.id : "export"}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      showToast("Trace exported successfully!", "success");
    });

    // Keyboard Shortcuts
    window.addEventListener("keydown", (e) => {
      // Don't intercept if user is typing in inputs or textareas
      const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || tag === "select") {
        if (e.key === "Escape") document.activeElement.blur();
        return;
      }

      switch (e.key) {
        case "ArrowRight":
        case "l":
          e.preventDefault();
          stepNext();
          break;
        case "ArrowLeft":
        case "h":
          e.preventDefault();
          stepPrev();
          break;
        case " ":
          e.preventDefault();
          togglePlay();
          break;
        case "Home":
          e.preventDefault();
          stepFirst();
          break;
        case "End":
          e.preventDefault();
          stepLast();
          break;
        case "1":
          document.getElementById("tab-btn-vars").click();
          break;
        case "2":
          document.getElementById("tab-btn-ast").click();
          break;
        case "3":
          document.getElementById("tab-btn-stack").click();
          break;
        case "4":
          document.getElementById("tab-btn-events").click();
          break;
        case "Escape":
          el.modalTrace.removeAttribute("open");
          el.modalShortcuts.removeAttribute("open");
          break;
      }
    });
  }

  // ==========================================================================
  // Helper Utilities
  // ==========================================================================

  function getLatestSnapshotVariables() {
    if (state.events.length === 0) return {};
    const ev = state.events[state.currentEventIndex];
    const snap = state.snapshotCache.get(ev.id);
    return snap ? snap.variables : {};
  }

  function formatDisplayValue(val) {
    if (val === null) return "None";
    if (val === undefined) return "undefined";
    if (typeof val === "object") {
      if (val.__type__) {
        return `<${val.__type__}>`;
      }
      try {
        return JSON.stringify(val);
      } catch {
        return String(val);
      }
    }
    if (typeof val === "string") return `"${val}"`;
    return String(val);
  }

  function inferType(val) {
    if (val === null || val === undefined) return "None";
    if (typeof val === "boolean") return "bool";
    if (typeof val === "number") return Number.isInteger(val) ? "int" : "float";
    if (typeof val === "string") return "str";
    if (Array.isArray(val)) return "list";
    if (typeof val === "object") {
      if (val.__type__) return val.__type__.toLowerCase();
      return "dict";
    }
    return "obj";
  }

  function escapeHtml(str) {
    if (typeof str !== "string") str = String(str);
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function clearWorkspace() {
    el.sumTarget.textContent = "-";
    el.sumStatus.textContent = "-";
    el.sumEvents.textContent = "0";
    el.codeContainer.innerHTML = '<div class="code-placeholder"><p>No trace loaded. Trace a script or select a database.</p></div>';
    el.variablesTbody.innerHTML = '<tr><td colspan="4" class="empty-state">No variables.</td></tr>';
  }

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    el.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 3200);
  }

  // Kickstart Application
  window.addEventListener("DOMContentLoaded", init);
})();
