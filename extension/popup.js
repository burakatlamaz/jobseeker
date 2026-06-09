const startQueueTestBtn = document.getElementById("startQueueTestBtn");
const queueFileInput = document.getElementById("queueFileInput");
const importQueueBtn = document.getElementById("importQueueBtn");
const startImportedQueueBtn = document.getElementById("startImportedQueueBtn");
const parseDetailsBtn = document.getElementById("parseDetailsBtn");
const stopAutoBtn = document.getElementById("stopAutoBtn");
const showBtn = document.getElementById("showBtn");
const exportBtn = document.getElementById("exportBtn");
const exportParsedBtn = document.getElementById("exportParsedBtn");
const clearBtn = document.getElementById("clearBtn");
const statusDiv = document.getElementById("status");
const outputPre = document.getElementById("output");

function setStatus(message) {
  statusDiv.textContent = message;
}

function setOutput(text) {
  outputPre.textContent = text;
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({
    active: true,
    currentWindow: true
  });
  return tabs[0];
}

async function refreshStatus() {
  const result = await chrome.storage.local.get([
    "collectedJobRecords",
    "currentRunRecords",
    "parsedJobRecords",
    "importedQueue",
    "crawlState",
    "queueState",
    "detailState",
    "lastExportInfo"
  ]);

  const pool = result.collectedJobRecords || [];
  const run = result.currentRunRecords || [];
  const parsed = result.parsedJobRecords || [];
  const importedQueue = result.importedQueue || [];
  const crawlState = result.crawlState || null;
  const queueState = result.queueState || null;
  const detailState = result.detailState || null;
  const lastExportInfo = result.lastExportInfo || null;

  let text = "Total pool records: " + pool.length;
  text += "\nCurrent run records: " + run.length;
  text += "\nParsed detail records: " + parsed.length;
  text += "\nImported queue URLs: " + importedQueue.length;

  if (crawlState && crawlState.running) {
    text += "\nRunning: " + Boolean(crawlState.running);
    text += "\nFinished: " + Boolean(crawlState.finished);
    text += "\nPages done: " + (crawlState.pagesDone || 0);
    text += "\nTarget pages: " + (crawlState.maxPages || 0);

    if (crawlState.stopReason) {
      text += "\nStop reason: " + crawlState.stopReason;
    }

    if (Array.isArray(crawlState.pageStats) && crawlState.pageStats.length) {
      text += "\n\nPer-page found counts:";
      for (const item of crawlState.pageStats) {
        text += "\n- " + item.foundOnPage + " urls";
      }
    }
  }

  if (queueState) {
    text += "\n\nQueue running: " + Boolean(queueState.running);
    text += "\nQueue finished: " + Boolean(queueState.finished);
    text += "\nQueue index: " + (queueState.currentIndex || 0) + "/" + (queueState.total || 0);
    text += "\nQueue pages done: " + (queueState.pagesDone || 0);
    if (queueState.stopReason) {
      text += "\nQueue stop reason: " + queueState.stopReason;
    }
    if (Array.isArray(queueState.pageStats) && queueState.pageStats.length) {
      text += "\n\nQueue page counts:";
      for (const item of queueState.pageStats.slice(-12)) {
        text += "\n- " + item.source + " p" + item.pageNumber + ": " + item.foundOnPage + " urls";
      }
    }
  }

  if (detailState) {
    text += "\n\nDetail running: " + Boolean(detailState.running);
    text += "\nDetail finished: " + Boolean(detailState.finished);
    text += "\nDetail index: " + (detailState.currentIndex || 0) + "/" + (detailState.total || 0);
    text += "\nDetail pages done: " + (detailState.pagesDone || 0);
    if (detailState.stopReason) {
      text += "\nDetail stop reason: " + detailState.stopReason;
    }
    if (Array.isArray(detailState.pageStats) && detailState.pageStats.length) {
      text += "\n\nDetail recent:";
      for (const item of detailState.pageStats.slice(-8)) {
        text += "\n- " + item.source + ": " + (item.parseSuccess ? "ok" : "fail");
      }
    }
  }

  if (lastExportInfo) {
    text += "\n\nLast export file: " + lastExportInfo.filename;
    text += "\nLast export count: " + lastExportInfo.exportedCount;
    text += "\nLast export at: " + lastExportInfo.exportedAt;
  }

  setStatus(text);
}

startQueueTestBtn.addEventListener("click", async () => {
  try {
    const response = await chrome.runtime.sendMessage({
      type: "START_TEST_QUEUE"
    });

    if (!response || !response.success) {
      setStatus("Could not start test queue: " + (response?.error || "Unknown error"));
      return;
    }

    await refreshStatus();
  } catch (error) {
    setStatus("Queue start error: " + error.message);
  }
});

function parseQueueFileText(text) {
  const clean = text.trim();
  if (!clean) return [];

  if (clean.startsWith("[")) {
    return JSON.parse(clean);
  }

  return clean
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

importQueueBtn.addEventListener("click", async () => {
  try {
    const file = queueFileInput.files && queueFileInput.files[0];
    if (!file) {
      setStatus("Choose a queue JSON/JSONL file first.");
      return;
    }

    const text = await file.text();
    const rows = parseQueueFileText(text);
    const queue = rows
      .filter((row) => row && row.url && row.source)
      .map((row) => ({
        source: row.source,
        query: row.query || row.search_query || null,
        location: row.location || row.search_location || null,
        pageNumber: Number(row.pageNumber || row.result_page_number || 1),
        url: row.url
      }));

    await chrome.storage.local.set({ importedQueue: queue });
    setStatus("Imported queue URLs: " + queue.length);
    await refreshStatus();
  } catch (error) {
    setStatus("Queue import failed: " + error.message);
  }
});

startImportedQueueBtn.addEventListener("click", async () => {
  try {
    const response = await chrome.runtime.sendMessage({
      type: "START_IMPORTED_QUEUE"
    });

    if (!response || !response.success) {
      setStatus("Could not start imported queue: " + (response?.error || "Unknown error"));
      return;
    }

    await refreshStatus();
  } catch (error) {
    setStatus("Imported queue start error: " + error.message);
  }
});

parseDetailsBtn.addEventListener("click", async () => {
  try {
    const response = await chrome.runtime.sendMessage({
      type: "START_DETAIL_QUEUE"
    });

    if (!response || !response.success) {
      setStatus("Could not start detail parsing: " + (response?.error || "Unknown error"));
      return;
    }

    await refreshStatus();
  } catch (error) {
    setStatus("Detail parse start error: " + error.message);
  }
});

stopAutoBtn.addEventListener("click", async () => {
  try {
    const tab = await getActiveTab();

    let response = null;

    try {
      response = await chrome.runtime.sendMessage({
        type: "STOP_QUEUE"
      });
    } catch (error) {
      response = null;
    }

    try {
      await chrome.runtime.sendMessage({
        type: "STOP_DETAIL_QUEUE"
      });
    } catch (error) {
      // Detail queue may not be running.
    }

    if (tab && tab.id) {
      try {
        await chrome.tabs.sendMessage(tab.id, {
          type: "STOP_AUTO_CRAWL"
        });
      } catch (error) {
        // Some queue pages do not support the old LinkedIn auto-crawl message.
      }
    }

    if (!response || !response.success) {
      setStatus("Stop signal sent where possible.");
      await refreshStatus();
      return;
    }

    await refreshStatus();
  } catch (error) {
    setStatus("Error: " + error.message);
  }
});

showBtn.addEventListener("click", async () => {
  const result = await chrome.storage.local.get(["collectedJobRecords"]);
  const pool = result.collectedJobRecords || [];

  await refreshStatus();
  setOutput(JSON.stringify(pool, null, 2));
});

exportBtn.addEventListener("click", async () => {
  const result = await chrome.storage.local.get([
    "currentRunRecords",
    "crawlState",
    "queueState"
  ]);
  const runRecords = result.currentRunRecords || [];
  const queueState = result.queueState || {};
  const crawlState = result.crawlState || {};
  const runId = queueState.runId || crawlState.runId;

  if (!runRecords.length || !runId) {
    setStatus("No current run records to export.");
    return;
  }

  try {
    const response = await chrome.runtime.sendMessage({
      type: "EXPORT_RUN_FILE",
      runId,
      records: runRecords
    });

    if (!response || !response.success) {
      setStatus("Export failed: " + (response?.error || "Unknown error"));
      return;
    }

    setStatus(
      "Exported " +
        response.exportedCount +
        " records\nFile: " +
        response.filename
    );

    await refreshStatus();
  } catch (error) {
    setStatus("Export failed: " + error.message);
  }
});

exportParsedBtn.addEventListener("click", async () => {
  const result = await chrome.storage.local.get(["parsedJobRecords", "detailState"]);
  const parsedRecords = result.parsedJobRecords || [];
  const detailState = result.detailState || {};
  const runId = detailState.runId || Date.now();

  if (!parsedRecords.length) {
    setStatus("No parsed detail records to export.");
    return;
  }

  try {
    const response = await chrome.runtime.sendMessage({
      type: "EXPORT_DETAIL_FILE",
      runId,
      records: parsedRecords
    });

    if (!response || !response.success) {
      setStatus("Parsed export failed: " + (response?.error || "Unknown error"));
      return;
    }

    setStatus(
      "Exported " +
        response.exportedCount +
        " parsed records\nFile: " +
        response.filename
    );

    await refreshStatus();
  } catch (error) {
    setStatus("Parsed export failed: " + error.message);
  }
});

clearBtn.addEventListener("click", async () => {
  await chrome.storage.local.set({
    collectedJobRecords: [],
    currentRunRecords: [],
    parsedJobRecords: [],
    importedQueue: [],
    crawlState: null,
    queueState: null,
    detailState: null,
    lastExportInfo: null
  });

  setStatus("All saved records cleared.");
  setOutput("");
});

refreshStatus();
setInterval(refreshStatus, 1500);
