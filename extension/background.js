chrome.runtime.onInstalled.addListener(() => {
  console.log("Jobseeker extension installed.");
});

function toJsonl(records) {
  return records.map((item) => JSON.stringify(item)).join("\n");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const TEST_QUEUE = [
  {
    source: "indeed",
    query: "Working Student",
    location: "Darmstadt",
    pageNumber: 1,
    url: "https://de.indeed.com/jobs?q=Working+Student&l=Darmstadt&fromage=14&sort=date"
  },
  {
    source: "stepstone",
    query: "Working Student",
    location: "Darmstadt",
    pageNumber: 1,
    url: "https://www.stepstone.de/jobs?what=Working+Student&where=Darmstadt&radius=30&sort=2"
  },
  {
    source: "linkedin",
    query: "Working Student",
    location: "Darmstadt",
    pageNumber: 1,
    url: "https://www.linkedin.com/jobs/search/?keywords=Working+Student&location=Darmstadt&f_TPR=r1209600&sortBy=DD"
  },
  {
    source: "xing",
    query: "Working Student",
    location: "Darmstadt",
    pageNumber: 1,
    url: "https://www.xing.com/jobs/search?keywords=Working+Student&location=Darmstadt"
  },
  {
    source: "arbeitsagentur",
    query: "Working Student",
    location: "Darmstadt",
    pageNumber: 1,
    url: "https://www.arbeitsagentur.de/jobsuche/suche?was=Working+Student&wo=Darmstadt&angebotsart=1"
  },
  {
    source: "stellenwerk",
    query: "Werkstudent",
    location: "Darmstadt",
    pageNumber: 1,
    url: "https://www.stellenwerk.de/darmstadt?_q=werkstudent"
  },
  {
    source: "indeed",
    query: "Working Student",
    location: "Darmstadt",
    pageNumber: 2,
    url: "https://de.indeed.com/jobs?q=Working+Student&l=Darmstadt&fromage=14&sort=date&start=10"
  },
  {
    source: "stepstone",
    query: "Working Student",
    location: "Darmstadt",
    pageNumber: 2,
    url: "https://www.stepstone.de/jobs?what=Working+Student&where=Darmstadt&radius=30&sort=2&page=2"
  },
  {
    source: "linkedin",
    query: "Working Student",
    location: "Darmstadt",
    pageNumber: 2,
    url: "https://www.linkedin.com/jobs/search/?keywords=Working+Student&location=Darmstadt&f_TPR=r1209600&sortBy=DD&start=25"
  },
  {
    source: "xing",
    query: "Working Student",
    location: "Darmstadt",
    pageNumber: 2,
    url: "https://www.xing.com/jobs/search?keywords=Working+Student&location=Darmstadt&page=2"
  },
  {
    source: "stellenwerk",
    query: "Werkstudent",
    location: "Darmstadt",
    pageNumber: 2,
    url: "https://www.stellenwerk.de/darmstadt?_q=werkstudent&pagination%5Bstart%5D=10"
  }
];

function tabFinishedLoading(tabId) {
  return new Promise((resolve) => {
    const timeoutId = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }, 30000);

    function listener(updatedTabId, changeInfo) {
      if (updatedTabId === tabId && changeInfo.status === "complete") {
        clearTimeout(timeoutId);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    }

    chrome.tabs.onUpdated.addListener(listener);
  });
}

function mergeRecords(oldRecords, newRecords) {
  const map = new Map();

  for (const record of oldRecords || []) {
    map.set(record.url, record);
  }

  for (const record of newRecords || []) {
    if (!map.has(record.url)) {
      map.set(record.url, record);
    }
  }

  return Array.from(map.values());
}

function mergeRecordsByKey(oldRecords, newRecords, keyName) {
  const map = new Map();

  for (const record of oldRecords || []) {
    map.set(record[keyName] || record.url, record);
  }

  for (const record of newRecords || []) {
    const key = record[keyName] || record.url;
    if (!map.has(key)) {
      map.set(key, record);
    }
  }

  return Array.from(map.values());
}

async function saveQueueRecords(newRecords) {
  const result = await chrome.storage.local.get(["collectedJobRecords", "currentRunRecords"]);
  const oldPool = result.collectedJobRecords || [];
  const oldRun = result.currentRunRecords || [];

  const mergedPool = mergeRecords(oldPool, newRecords);
  const mergedRun = mergeRecords(oldRun, newRecords);

  await chrome.storage.local.set({
    collectedJobRecords: mergedPool,
    currentRunRecords: mergedRun
  });

  return {
    totalPoolCount: mergedPool.length,
    totalRunCount: mergedRun.length,
    addedToPool: mergedPool.length - oldPool.length,
    addedToRun: mergedRun.length - oldRun.length
  };
}

async function collectCurrentTab(tabId, queueItem, runId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, {
      type: "COLLECT_JOB_URLS",
      queueItem,
      runId
    });

    if (!response || !response.success) {
      return {
        success: false,
        records: [],
        error: response?.error || "No response from content script"
      };
    }

    return response;
  } catch (error) {
    return {
      success: false,
      records: [],
      error: error.message
    };
  }
}

async function parseCurrentTab(tabId, sourceRecord, runId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, {
      type: "PARSE_JOB_DETAIL",
      sourceRecord,
      runId
    });

    if (!response || !response.success) {
      return {
        success: false,
        record: null,
        error: response?.error || "No response from content script"
      };
    }

    return response;
  } catch (error) {
    return {
      success: false,
      record: null,
      error: error.message
    };
  }
}

async function saveParsedDetailRecord(record) {
  if (!record) {
    return {
      totalParsedCount: 0,
      addedToParsed: 0
    };
  }

  const result = await chrome.storage.local.get(["parsedJobRecords"]);
  const oldRecords = result.parsedJobRecords || [];
  const merged = mergeRecordsByKey(oldRecords, [record], "source_job_url");

  await chrome.storage.local.set({
    parsedJobRecords: merged
  });

  return {
    totalParsedCount: merged.length,
    addedToParsed: merged.length - oldRecords.length
  };
}

async function runQueue(queue) {
  const runId = Date.now();

  await chrome.storage.local.set({
    currentRunRecords: [],
    parsedJobRecords: [],
    detailState: null,
    queueState: {
      running: true,
      finished: false,
      runId,
      total: queue.length,
      currentIndex: 0,
      pagesDone: 0,
      startedAt: new Date().toISOString(),
      finishedAt: null,
      stopReason: null,
      pageStats: []
    }
  });

  const created = await chrome.tabs.create({
    url: queue[0].url,
    active: true
  });
  const tabId = created.id;

  for (let index = 0; index < queue.length; index += 1) {
    const item = queue[index];

    const stateResult = await chrome.storage.local.get(["queueState"]);
    const currentState = stateResult.queueState || {};
    if (!currentState.running) {
      break;
    }

    await chrome.storage.local.set({
      queueState: {
        ...currentState,
        currentIndex: index + 1,
        lastUrl: item.url,
        lastSource: item.source,
        lastUpdatedAt: new Date().toISOString()
      }
    });

    await chrome.tabs.update(tabId, {
      url: item.url,
      active: true
    });
    await tabFinishedLoading(tabId);
    await sleep(3500);

    const collection = await collectCurrentTab(tabId, item, runId);
    const saveInfo = await saveQueueRecords(collection.records || []);

    const afterStateResult = await chrome.storage.local.get(["queueState"]);
    const afterState = afterStateResult.queueState || {};
    const pageStats = afterState.pageStats || [];
    pageStats.push({
      source: item.source,
      query: item.query,
      location: item.location,
      pageNumber: item.pageNumber,
      pageUrl: item.url,
      foundOnPage: (collection.records || []).length,
      addedToRun: saveInfo.addedToRun,
      error: collection.success ? null : collection.error,
      checkedAt: new Date().toISOString()
    });

    await chrome.storage.local.set({
      queueState: {
        ...afterState,
        pageStats,
        pagesDone: pageStats.length,
        currentRunCount: saveInfo.totalRunCount,
        totalPoolCount: saveInfo.totalPoolCount,
        lastUpdatedAt: new Date().toISOString()
      }
    });
  }

  const finalStateResult = await chrome.storage.local.get(["queueState"]);
  const finalState = finalStateResult.queueState || {};
  await chrome.storage.local.set({
    queueState: {
      ...finalState,
      running: false,
      finished: true,
      finishedAt: new Date().toISOString(),
      stopReason: finalState.stopReason || "Queue completed"
    }
  });
}

async function runDetailQueue(records) {
  const runId = Date.now();
  const detailRecords = (records || []).filter((record) => record && record.url);

  await chrome.storage.local.set({
    parsedJobRecords: [],
    detailState: {
      running: true,
      finished: false,
      runId,
      total: detailRecords.length,
      currentIndex: 0,
      pagesDone: 0,
      startedAt: new Date().toISOString(),
      finishedAt: null,
      stopReason: null,
      pageStats: []
    }
  });

  if (!detailRecords.length) {
    await chrome.storage.local.set({
      detailState: {
        running: false,
        finished: true,
        runId,
        total: 0,
        currentIndex: 0,
        pagesDone: 0,
        startedAt: new Date().toISOString(),
        finishedAt: new Date().toISOString(),
        stopReason: "No URLs to parse",
        pageStats: []
      }
    });
    return;
  }

  const created = await chrome.tabs.create({
    url: detailRecords[0].url,
    active: true
  });
  const tabId = created.id;

  for (let index = 0; index < detailRecords.length; index += 1) {
    const item = detailRecords[index];

    const stateResult = await chrome.storage.local.get(["detailState"]);
    const currentState = stateResult.detailState || {};
    if (!currentState.running) {
      break;
    }

    await chrome.storage.local.set({
      detailState: {
        ...currentState,
        currentIndex: index + 1,
        lastUrl: item.url,
        lastSource: item.source || "unknown",
        lastUpdatedAt: new Date().toISOString()
      }
    });

    await chrome.tabs.update(tabId, {
      url: item.url,
      active: true
    });
    await tabFinishedLoading(tabId);
    await sleep(4500);

    const parsed = await parseCurrentTab(tabId, item, runId);
    const saveInfo = await saveParsedDetailRecord(parsed.record || null);

    const afterStateResult = await chrome.storage.local.get(["detailState"]);
    const afterState = afterStateResult.detailState || {};
    const pageStats = afterState.pageStats || [];
    pageStats.push({
      source: item.source || "unknown",
      sourceUrl: item.url,
      parseSuccess: Boolean(parsed.record?.parse_success),
      title: parsed.record?.title || null,
      company: parsed.record?.company || null,
      error: parsed.success ? null : parsed.error,
      checkedAt: new Date().toISOString()
    });

    await chrome.storage.local.set({
      detailState: {
        ...afterState,
        pageStats,
        pagesDone: pageStats.length,
        parsedCount: saveInfo.totalParsedCount,
        lastUpdatedAt: new Date().toISOString()
      }
    });
  }

  const finalStateResult = await chrome.storage.local.get(["detailState"]);
  const finalState = finalStateResult.detailState || {};
  await chrome.storage.local.set({
    detailState: {
      ...finalState,
      running: false,
      finished: true,
      finishedAt: new Date().toISOString(),
      stopReason: finalState.stopReason || "Detail queue completed"
    }
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "EXPORT_RUN_FILE") {
    (async () => {
      try {
        const runId = message.runId;
        const records = message.records || [];

        if (!runId || !Array.isArray(records)) {
          sendResponse({
            success: false,
            error: "Missing runId or records"
          });
          return;
        }

        const jsonl = toJsonl(records);
        const dataUrl =
          "data:application/x-ndjson;charset=utf-8," +
          encodeURIComponent(jsonl);

        const filename = `job-search-system/raw_exports/job_run_${runId}.jsonl`;

        const downloadId = await chrome.downloads.download({
          url: dataUrl,
          filename: filename,
          saveAs: false,
          conflictAction: "uniquify"
        });

        const lastExportInfo = {
          runId,
          filename,
          downloadId,
          exportedCount: records.length,
          exportedAt: new Date().toISOString()
        };

        await chrome.storage.local.set({ lastExportInfo });

        sendResponse({
          success: true,
          filename,
          downloadId,
          exportedCount: records.length
        });
      } catch (error) {
        console.error("EXPORT_RUN_FILE error:", error);
        sendResponse({
          success: false,
          error: error.message
        });
      }
    })();

    return true;
  }

  if (message && message.type === "EXPORT_DETAIL_FILE") {
    (async () => {
      try {
        const runId = message.runId;
        const records = message.records || [];

        if (!runId || !Array.isArray(records)) {
          sendResponse({
            success: false,
            error: "Missing runId or records"
          });
          return;
        }

        const jsonl = toJsonl(records);
        const dataUrl =
          "data:application/x-ndjson;charset=utf-8," +
          encodeURIComponent(jsonl);

        const filename = `job-search-system/parsed_exports/parsed_job_details_${runId}.jsonl`;

        const downloadId = await chrome.downloads.download({
          url: dataUrl,
          filename,
          saveAs: false,
          conflictAction: "uniquify"
        });

        const lastExportInfo = {
          runId,
          filename,
          downloadId,
          exportedCount: records.length,
          exportedAt: new Date().toISOString()
        };

        await chrome.storage.local.set({ lastExportInfo });

        sendResponse({
          success: true,
          filename,
          downloadId,
          exportedCount: records.length
        });
      } catch (error) {
        console.error("EXPORT_DETAIL_FILE error:", error);
        sendResponse({
          success: false,
          error: error.message
        });
      }
    })();

    return true;
  }

  if (message && message.type === "START_TEST_QUEUE") {
    (async () => {
      try {
        sendResponse({ success: true });
        await runQueue(TEST_QUEUE);
      } catch (error) {
        console.error("START_TEST_QUEUE error:", error);
      }
    })();

    return true;
  }

  if (message && message.type === "START_IMPORTED_QUEUE") {
    (async () => {
      try {
        const result = await chrome.storage.local.get(["importedQueue"]);
        const queue = result.importedQueue || [];
        if (!queue.length) {
          sendResponse({ success: false, error: "No imported queue found" });
          return;
        }

        sendResponse({ success: true, count: queue.length });
        await runQueue(queue);
      } catch (error) {
        console.error("START_IMPORTED_QUEUE error:", error);
      }
    })();

    return true;
  }

  if (message && message.type === "START_DETAIL_QUEUE") {
    (async () => {
      try {
        const result = await chrome.storage.local.get([
          "currentRunRecords",
          "collectedJobRecords"
        ]);
        const records = (result.currentRunRecords || []).length
          ? result.currentRunRecords
          : result.collectedJobRecords || [];

        sendResponse({ success: true, count: records.length });
        await runDetailQueue(records);
      } catch (error) {
        console.error("START_DETAIL_QUEUE error:", error);
      }
    })();

    return true;
  }

  if (message && message.type === "STOP_QUEUE") {
    (async () => {
      const result = await chrome.storage.local.get(["queueState"]);
      const queueState = result.queueState || {};
      await chrome.storage.local.set({
        queueState: {
          ...queueState,
          running: false,
          finished: true,
          finishedAt: new Date().toISOString(),
          stopReason: "Stopped by user"
        }
      });
      sendResponse({ success: true });
    })();

    return true;
  }

  if (message && message.type === "STOP_DETAIL_QUEUE") {
    (async () => {
      const result = await chrome.storage.local.get(["detailState"]);
      const detailState = result.detailState || {};
      await chrome.storage.local.set({
        detailState: {
          ...detailState,
          running: false,
          finished: true,
          finishedAt: new Date().toISOString(),
          stopReason: "Stopped by user"
        }
      });
      sendResponse({ success: true });
    })();

    return true;
  }
});
