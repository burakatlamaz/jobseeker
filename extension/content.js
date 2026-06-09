let lastSeenUrl = location.href;
let isRunningNow = false;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeUrlWithoutTracking(url, allowedParams = []) {
  try {
    const parsed = new URL(url);
    const nextSearch = new URLSearchParams();

    for (const key of allowedParams) {
      const value = parsed.searchParams.get(key);
      if (value) {
        nextSearch.set(key, value);
      }
    }

    parsed.search = nextSearch.toString();
    parsed.hash = "";

    let clean = parsed.toString();
    if (clean.endsWith("/")) {
      clean = clean.slice(0, -1);
    }

    return clean;
  } catch (error) {
    return null;
  }
}

function detectJobSource(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase();
    const path = parsed.pathname.toLowerCase();

    if (host.includes("linkedin.com") && path.includes("/jobs/view/")) {
      return "linkedin";
    }

    if (host.includes("indeed.com") && (path.includes("/viewjob") || path.includes("/rc/clk"))) {
      return "indeed";
    }

    if (host.includes("stepstone.de") && path.includes("/stellenangebote--")) {
      return "stepstone";
    }

    if (host.includes("xing.com") && path.startsWith("/jobs/") && !path.startsWith("/jobs/search")) {
      return "xing";
    }

    if (host.includes("arbeitsagentur.de") && path.includes("/jobsuche/jobdetail/")) {
      return "arbeitsagentur";
    }

    if (host.includes("stellenwerk.de")) {
      const parts = path.split("/").filter(Boolean);
      const knownLocations = new Set(["darmstadt", "frankfurt", "heidelberg", "hamburg", "mainz", "wiesbaden"]);
      if (parts.length >= 2 && knownLocations.has(parts[0]) && /\d/.test(parts[parts.length - 1])) {
        return "stellenwerk";
      }
    }

    return null;
  } catch (error) {
    return null;
  }
}

function normalizeJobUrl(url, source) {
  try {
    const parsed = new URL(url);

    if (source === "indeed") {
      const jobKey = parsed.searchParams.get("jk");
      if (!jobKey) return null;
      return `https://de.indeed.com/viewjob?jk=${jobKey}`;
    }

    if (source === "linkedin") {
      const parts = parsed.pathname.split("/").filter(Boolean);
      const viewIndex = parts.indexOf("view");
      const jobId = viewIndex >= 0 ? parts[viewIndex + 1] : null;
      if (!jobId) return null;
      return `https://www.linkedin.com/jobs/view/${jobId}`;
    }

    if (source === "stepstone" || source === "xing" || source === "arbeitsagentur" || source === "stellenwerk") {
      return normalizeUrlWithoutTracking(url);
    }

    return null;
  } catch (error) {
    return null;
  }
}

function textFrom(container, selectors) {
  if (!container) return null;

  for (const selector of selectors) {
    const match = container.querySelector(selector);
    const text = match && match.innerText ? match.innerText.trim() : "";
    if (text) return text;
  }

  return null;
}

function firstPageText(selectors) {
  for (const selector of selectors) {
    const match = document.querySelector(selector);
    const text = match && match.innerText ? match.innerText.trim() : "";
    if (text) return text;
  }

  return null;
}

function allPageTexts(selectors) {
  const values = [];
  const seen = new Set();

  for (const selector of selectors) {
    for (const match of document.querySelectorAll(selector)) {
      const text = match && match.innerText ? match.innerText.trim() : "";
      if (text && !seen.has(text)) {
        values.push(text);
        seen.add(text);
      }
    }
  }

  return values;
}

function getDomain(url) {
  if (!url) return null;

  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, "");
  } catch (error) {
    return null;
  }
}

function trimDetailNoise(text) {
  if (!text) return null;

  const markers = [
    "People also viewed",
    "Jobs you may like",
    "Similar jobs",
    "Recommended for you",
    "Browse jobs",
    "Company photos",
    "More jobs",
    "Ähnliche Jobs",
    "Weitere Jobs",
    "Empfohlene Jobs"
  ];

  let trimmed = text.trim();
  for (const marker of markers) {
    const index = trimmed.indexOf(marker);
    if (index > 0) {
      trimmed = trimmed.slice(0, index).trim();
    }
  }

  return trimmed || null;
}

function extractDetailTitle(source) {
  const selectors = {
    linkedin: [
      ".job-details-jobs-unified-top-card__job-title h1",
      ".top-card-layout__title",
      "h1"
    ],
    indeed: [
      "h1[data-testid='jobsearch-JobInfoHeader-title']",
      "[data-testid='jobsearch-JobInfoHeader-title'] h1",
      "h1"
    ],
    stepstone: [
      "[data-at='header-job-title']",
      "[data-testid='job-title']",
      "h1"
    ],
    xing: ["h1", "[data-testid*='job-title']"],
    arbeitsagentur: ["h1", "[data-testid*='beruf']"],
    stellenwerk: ["h1", ".node-title"]
  };

  return firstPageText(selectors[source] || ["h1"]);
}

function extractDetailCompany(source) {
  const selectors = {
    linkedin: [
      ".job-details-jobs-unified-top-card__company-name a",
      ".job-details-jobs-unified-top-card__company-name",
      ".topcard__org-name-link"
    ],
    indeed: [
      "[data-testid='inlineHeader-companyName']",
      "[data-company-name='true']",
      ".jobsearch-CompanyInfoContainer a",
      ".jobsearch-CompanyInfoContainer"
    ],
    stepstone: [
      "[data-at='header-company-name']",
      "[data-testid='company-name']",
      "a[href*='/cmp/']"
    ],
    xing: ["[data-testid*='company']", "a[href*='/companies/']"],
    arbeitsagentur: ["[data-testid*='arbeitgeber']", "[data-testid*='company']"],
    stellenwerk: [".field--name-field-company", "[class*='company']"]
  };

  return firstPageText(selectors[source] || ["[class*='company']"]);
}

function extractDetailLocation(source) {
  const selectors = {
    linkedin: [
      ".job-details-jobs-unified-top-card__primary-description-container",
      ".topcard__flavor--bullet"
    ],
    indeed: [
      "[data-testid='job-location']",
      "[data-testid='inlineHeader-companyLocation']",
      ".jobsearch-JobInfoHeader-subtitle div"
    ],
    stepstone: [
      "[data-at='header-job-location']",
      "[data-testid='job-location']",
      "[class*='location']"
    ],
    xing: ["[data-testid*='location']", "[class*='location']"],
    arbeitsagentur: ["[data-testid*='arbeitsort']", "[data-testid*='location']"],
    stellenwerk: [".field--name-field-location", "[class*='location']"]
  };

  return firstPageText(selectors[source] || ["[class*='location']"]);
}

function extractDetailDescription(source) {
  const selectors = {
    linkedin: [
      ".jobs-description__content",
      ".jobs-box__html-content",
      ".jobs-description-content__text",
      ".show-more-less-html__markup"
    ],
    indeed: [
      "#jobDescriptionText",
      "[data-testid='jobsearch-JobComponent-description']",
      ".jobsearch-jobDescriptionText"
    ],
    stepstone: [
      "[data-at='job-ad-content']",
      "[data-testid='job-description']",
      "article",
      "main section"
    ],
    xing: ["[data-testid*='description']", "article", "main"],
    arbeitsagentur: [
      "[data-testid*='stellenbeschreibung']",
      "[data-testid*='description']",
      "main"
    ],
    stellenwerk: [".field--name-body", "article", "main"]
  };

  const candidates = allPageTexts(selectors[source] || ["article", "main"]);
  const best = candidates
    .filter((text) => text.length > 80)
    .sort((a, b) => b.length - a.length)[0];

  if (best) {
    return {
      text: trimDetailNoise(best),
      quality: "source_container"
    };
  }

  return {
    text: trimDetailNoise(document.body?.innerText || ""),
    quality: "fallback_body"
  };
}

function extractApplyUrl(source) {
  const selectors = [
    "a[href][aria-label*='Apply']",
    "a[href][aria-label*='Bewerben']",
    "a[href][data-control-name*='jobdetails_topcard']",
    "a[href][id*='apply']",
    "a[href][class*='apply']",
    "a[href*='/apply']",
    "a[href*='/bewerben']",
    "a[href*='/applystart']",
    "a[href*='indeedapply']"
  ];

  function allowedApplyUrl(url) {
    if (!url) return false;
    const domain = getDomain(url);
    const sourceDomains = {
      linkedin: ["linkedin.com"],
      indeed: ["indeed.com"],
      stepstone: ["stepstone.de"],
      xing: ["xing.com"],
      arbeitsagentur: ["arbeitsagentur.de"],
      stellenwerk: ["stellenwerk.de"]
    };

    if (url.includes("/safety/go")) return false;
    if ((sourceDomains[source] || []).some((sourceDomain) => domain?.includes(sourceDomain))) {
      return false;
    }

    return true;
  }

  for (const selector of selectors) {
    const match = document.querySelector(selector);
    const href = match?.getAttribute("href");
    if (href) {
      const url = new URL(href, location.href).toString();
      if (allowedApplyUrl(url)) return url;
    }
  }

  for (const anchor of Array.from(document.querySelectorAll("a[href]")).slice(0, 250)) {
    const text = `${anchor.innerText || ""} ${anchor.getAttribute("aria-label") || ""}`.toLowerCase();
    if (!["apply", "bewerben", "bewerbung"].some((word) => text.includes(word))) {
      continue;
    }

    const href = anchor.getAttribute("href");
    if (href) {
      const url = new URL(href, location.href).toString();
      if (allowedApplyUrl(url)) return url;
    }
  }

  return null;
}

function parseJobDetailFromPage(sourceRecord) {
  const source = sourceRecord?.source || detectJobSource(location.href) || "unknown";
  const now = new Date().toISOString();
  const description = extractDetailDescription(source);
  const title = extractDetailTitle(source) || sourceRecord?.title || null;
  const company = extractDetailCompany(source) || sourceRecord?.company || null;
  const locationRaw = extractDetailLocation(source) || sourceRecord?.location || null;
  const applyUrl = extractApplyUrl(source);

  return {
    url: sourceRecord?.url || location.href,
    source_job_url: sourceRecord?.url || location.href,
    source,
    sources: source ? [source] : [],
    search_urls: sourceRecord?.searchUrl ? [sourceRecord.searchUrl] : [],
    search_queries: sourceRecord?.searchQuery ? [sourceRecord.searchQuery] : [],
    title,
    company,
    location_raw: locationRaw,
    description_raw: description.text,
    workplace_type_raw: null,
    employment_type_raw: null,
    apply_url: applyUrl,
    parse_success: Boolean(title || company || locationRaw || description.text),
    parsed_at: now
  };
}

async function scrollForQueueCollection() {
  let stableRounds = 0;
  let previousY = window.scrollY;

  for (let i = 0; i < 10; i += 1) {
    window.scrollBy(0, Math.max(window.innerHeight * 0.9, 700));
    await sleep(600);

    const currentY = window.scrollY;
    const maxY = document.documentElement.scrollHeight - window.innerHeight;

    if (Math.abs(currentY - previousY) < 5 || currentY >= maxY - 20) {
      stableRounds += 1;
    } else {
      stableRounds = 0;
    }

    previousY = currentY;

    if (stableRounds >= 2) {
      break;
    }
  }
}

async function collectJobRecordsFromAnySupportedPage(queueItem, runId) {
  await sleep(1000);

  if (queueItem?.source === "linkedin") {
    const urls = await collectUrlsByScrolling();
    const now = new Date().toISOString();

    return urls.map((url) => ({
      source: "linkedin",
      url,
      collectedAt: now,
      searchUrl: location.href,
      runId,
      searchQuery: queueItem?.query || null,
      searchLocation: queueItem?.location || null,
      resultPageNumber: queueItem?.pageNumber || null,
      title: null,
      company: null,
      location: null
    }));
  }

  await scrollForQueueCollection();
  await sleep(500);

  const anchors = Array.from(document.querySelectorAll("a[href]"));
  const seen = new Set();
  const now = new Date().toISOString();
  const records = [];

  for (const anchor of anchors) {
    const detectedSource = detectJobSource(anchor.href);
    if (!detectedSource) continue;

    if (queueItem && queueItem.source && detectedSource !== queueItem.source) {
      continue;
    }

    const normalized = normalizeJobUrl(anchor.href, detectedSource);
    if (!normalized || seen.has(normalized)) continue;

    seen.add(normalized);

    const container = anchor.closest("article, li, div");
    records.push({
      source: detectedSource,
      url: normalized,
      collectedAt: now,
      searchUrl: location.href,
      runId,
      searchQuery: queueItem?.query || null,
      searchLocation: queueItem?.location || null,
      resultPageNumber: queueItem?.pageNumber || null,
      title:
        textFrom(container, [
          "h1",
          "h2",
          "h3",
          "[data-testid*='title']",
          "[class*='title']",
          "[class*='jobTitle']"
        ]) ||
        anchor.innerText?.trim() ||
        null,
      company: textFrom(container, [
        "[data-testid*='company']",
        "[class*='company']",
        "[class*='Company']"
      ]),
      location: textFrom(container, [
        "[data-testid*='location']",
        "[class*='location']",
        "[class*='Location']"
      ])
    });
  }

  return records;
}

function normalizeLinkedInJobUrl(url) {
  try {
    const parsed = new URL(url);
    parsed.search = "";
    parsed.hash = "";

    let clean = parsed.toString();
    if (clean.endsWith("/")) {
      clean = clean.slice(0, -1);
    }

    return clean;
  } catch (error) {
    return null;
  }
}

function normalizeSearchPageUrl(url) {
  try {
    const parsed = new URL(url);
    parsed.hash = "";

    let clean = parsed.toString();
    if (clean.endsWith("/")) {
      clean = clean.slice(0, -1);
    }

    return clean;
  } catch (error) {
    return url;
  }
}

function isLinkedInJobUrl(url) {
  if (!url) return false;

  try {
    const parsed = new URL(url);
    return (
      parsed.hostname.includes("linkedin.com") &&
      parsed.pathname.includes("/jobs/view/")
    );
  } catch (error) {
    return false;
  }
}

function collectJobUrlsFromPage() {
  const anchors = document.querySelectorAll('a[href*="/jobs/view/"]');
  const found = new Set();

  for (const anchor of anchors) {
    const href = anchor.href;

    if (!isLinkedInJobUrl(href)) {
      continue;
    }

    const normalized = normalizeLinkedInJobUrl(href);
    if (normalized) {
      found.add(normalized);
    }
  }

  return Array.from(found);
}

async function getStorage(keys) {
  return await chrome.storage.local.get(keys);
}

async function setStorage(data) {
  await chrome.storage.local.set(data);
}

function isElementScrollable(el) {
  if (!el) return false;

  const style = window.getComputedStyle(el);
  const overflowY = style.overflowY;

  return (
    (overflowY === "auto" || overflowY === "scroll") &&
    el.scrollHeight > el.clientHeight + 50
  );
}

function findJobListContainer() {
  const prioritySelectors = [
    ".jobs-search-results-list",
    ".jobs-search-results-list__list",
    ".scaffold-layout__list",
    ".scaffold-layout__list-detail-inner .scaffold-layout__list",
    ".jobs-search-two-pane__wrapper .scaffold-layout__list"
  ];

  for (const selector of prioritySelectors) {
    const el = document.querySelector(selector);
    if (isElementScrollable(el)) {
      console.log("Using priority scroll container:", selector, el);
      return el;
    }
  }

  const allElements = Array.from(document.querySelectorAll("div, section, main, ul"));
  let best = null;
  let bestScore = -1;

  for (const el of allElements) {
    if (!isElementScrollable(el)) continue;

    const jobLinksInside = el.querySelectorAll('a[href*="/jobs/view/"]').length;
    if (jobLinksInside < 3) continue;

    const score = jobLinksInside * 1000 + (el.scrollHeight - el.clientHeight);

    if (score > bestScore) {
      best = el;
      bestScore = score;
    }
  }

  if (best) {
    console.log("Using fallback scroll container:", best);
    return best;
  }

  console.log("Falling back to window scroll");
  return window;
}

/**
 * CRITICAL FIX:
 * Collect links during every scroll step, not only after the final position.
 * This solves virtualization where middle items disappear from the DOM.
 */
async function collectUrlsByScrolling() {
  const scrollTarget = findJobListContainer();
  const seen = new Set();

  // collect initial visible items
  for (const url of collectJobUrlsFromPage()) {
    seen.add(url);
  }

  let stableRounds = 0;
  let rounds = 0;
  let previousSeenCount = seen.size;
  let previousScrollTop =
    scrollTarget === window
      ? window.scrollY
      : scrollTarget.scrollTop;

  const maxRounds = 45;
  const stepSize =
    scrollTarget === window
      ? Math.max(window.innerHeight * 0.8, 500)
      : Math.max(scrollTarget.clientHeight * 0.8, 400);

  while (rounds < maxRounds) {
    if (scrollTarget === window) {
      window.scrollTo(0, window.scrollY + stepSize);
    } else {
      scrollTarget.scrollTop = scrollTarget.scrollTop + stepSize;
    }

    await sleep(350);

    const currentUrls = collectJobUrlsFromPage();
    for (const url of currentUrls) {
      seen.add(url);
    }

    const currentSeenCount = seen.size;
    const currentScrollTop =
      scrollTarget === window
        ? window.scrollY
        : scrollTarget.scrollTop;

    const maxScrollableTop =
      scrollTarget === window
        ? document.documentElement.scrollHeight - window.innerHeight
        : scrollTarget.scrollHeight - scrollTarget.clientHeight;

    const reachedBottom = currentScrollTop >= maxScrollableTop - 20;
    const countDidNotGrow = currentSeenCount === previousSeenCount;
    const scrollDidNotMove = Math.abs(currentScrollTop - previousScrollTop) < 5;

    console.log("Scroll step", {
      round: rounds + 1,
      currentSeenCount,
      currentScrollTop,
      maxScrollableTop,
      reachedBottom
    });

    if ((countDidNotGrow && scrollDidNotMove) || (reachedBottom && countDidNotGrow)) {
      stableRounds += 1;
    } else {
      stableRounds = 0;
    }

    previousSeenCount = currentSeenCount;
    previousScrollTop = currentScrollTop;

    if (stableRounds >= 3) {
      break;
    }

    rounds += 1;
  }

  // go back to top
  if (scrollTarget === window) {
    window.scrollTo(0, 0);
  } else {
    scrollTarget.scrollTop = 0;
  }

  await sleep(150);

  return Array.from(seen);
}

function normalizeTextForCompare(text) {
  return (text || "")
    .toLowerCase()
    .replaceAll("ä", "ae")
    .replaceAll("ö", "oe")
    .replaceAll("ü", "ue")
    .replaceAll("ß", "ss")
    .trim();
}

function findNextPageButton() {
  const candidates = Array.from(document.querySelectorAll("button, a"));

  for (const el of candidates) {
    const aria = normalizeTextForCompare(el.getAttribute("aria-label"));
    const text = normalizeTextForCompare(el.textContent);
    const cls = normalizeTextForCompare(el.className);

    const looksLikeNext =
      aria.includes("next") ||
      aria.includes("weiter") ||
      text === "next" ||
      text === "weiter" ||
      cls.includes("jobs-search-pagination__button--next");

    const disabled =
      el.disabled ||
      el.getAttribute("aria-disabled") === "true" ||
      cls.includes("disabled");

    if (looksLikeNext && !disabled) {
      return el;
    }
  }

  return null;
}

function mergePoolRecords(oldRecords, newRecords) {
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

function mergeRunRecords(oldRecords, newRecords) {
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

function buildRecordsFromUrls(urls, crawlState) {
  const now = new Date().toISOString();
  const searchUrl = normalizeSearchPageUrl(location.href);

  return urls.map((url) => ({
    url,
    collectedAt: now,
    searchUrl,
    runId: crawlState.runId
  }));
}

async function saveCollectedRecords(newRecords) {
  const result = await getStorage(["collectedJobRecords", "currentRunRecords"]);
  const oldPool = result.collectedJobRecords || [];
  const oldRun = result.currentRunRecords || [];

  const mergedPool = mergePoolRecords(oldPool, newRecords);
  const mergedRun = mergeRunRecords(oldRun, newRecords);

  await setStorage({
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

async function markCurrentPageProcessed(crawlState) {
  const currentPage = normalizeSearchPageUrl(location.href);
  const processedPages = crawlState.processedPages || [];

  if (!processedPages.includes(currentPage)) {
    processedPages.push(currentPage);
  }

  crawlState.processedPages = processedPages;
  crawlState.pagesDone = processedPages.length;
  crawlState.lastUpdatedAt = new Date().toISOString();

  await setStorage({ crawlState });
}

function currentPageAlreadyProcessed(crawlState) {
  const currentPage = normalizeSearchPageUrl(location.href);
  const processedPages = crawlState.processedPages || [];
  return processedPages.includes(currentPage);
}

async function exportCurrentRun(crawlState) {
  const result = await getStorage(["currentRunRecords"]);
  const records = result.currentRunRecords || [];

  if (!records.length) {
    return;
  }

  const response = await chrome.runtime.sendMessage({
    type: "EXPORT_RUN_FILE",
    runId: crawlState.runId,
    records
  });

  if (response && response.success) {
    const updatedStateResult = await getStorage(["crawlState"]);
    const updatedState = updatedStateResult.crawlState || {};

    updatedState.lastExport = {
      filename: response.filename,
      exportedCount: response.exportedCount,
      exportedAt: new Date().toISOString()
    };

    await setStorage({ crawlState: updatedState });
  } else {
    console.error("Export failed:", response?.error || "Unknown export error");
  }
}

async function finishCrawl(reason) {
  const result = await getStorage(["crawlState"]);
  const crawlState = result.crawlState || {};

  crawlState.running = false;
  crawlState.finished = true;
  crawlState.finishedAt = new Date().toISOString();
  crawlState.stopReason = reason;
  crawlState.lastUpdatedAt = new Date().toISOString();

  await setStorage({ crawlState });

  await exportCurrentRun(crawlState);

  console.log("Crawler finished:", reason);
}

async function runCrawlerOnce() {
  if (isRunningNow) {
    return;
  }

  isRunningNow = true;

  try {
    const result = await getStorage(["crawlState"]);
    const crawlState = result.crawlState;

    if (!crawlState || !crawlState.running) {
      isRunningNow = false;
      return;
    }

    if (currentPageAlreadyProcessed(crawlState)) {
      isRunningNow = false;
      return;
    }

    console.log("Crawler: processing page", location.href);

    await sleep(900);

    const urls = await collectUrlsByScrolling();
    const records = buildRecordsFromUrls(urls, crawlState);
    const saveInfo = await saveCollectedRecords(records);

    const pageStats = crawlState.pageStats || [];
    pageStats.push({
      pageUrl: normalizeSearchPageUrl(location.href),
      foundOnPage: urls.length,
      runCountAfterPage: saveInfo.totalRunCount,
      checkedAt: new Date().toISOString()
    });

    crawlState.pageStats = pageStats;
    await setStorage({ crawlState });

    console.log("Crawler: page collected", {
      pageFound: urls.length,
      runCount: saveInfo.totalRunCount,
      poolCount: saveInfo.totalPoolCount
    });

    await markCurrentPageProcessed(crawlState);

    const fresh = await getStorage(["crawlState"]);
    const updatedState = fresh.crawlState;

    if (!updatedState || !updatedState.running) {
      isRunningNow = false;
      return;
    }

    if ((updatedState.pagesDone || 0) >= (updatedState.maxPages || 0)) {
      await finishCrawl("Reached max pages");
      isRunningNow = false;
      return;
    }

    const nextButton = findNextPageButton();

    if (!nextButton) {
      await finishCrawl("Next page button not found");
      isRunningNow = false;
      return;
    }

    console.log("Crawler: going to next page");
    await sleep(250);
    nextButton.click();
  } catch (error) {
    console.error("Crawler error:", error);
    await finishCrawl("Error: " + error.message);
  }

  isRunningNow = false;
}

async function maybeContinueCrawler() {
  const result = await getStorage(["crawlState"]);
  const crawlState = result.crawlState;

  if (!crawlState || !crawlState.running) {
    return;
  }

  await runCrawlerOnce();
}

async function startAutoCrawl(maxPages) {
  const runId = Date.now();

  const crawlState = {
    running: true,
    finished: false,
    maxPages: maxPages,
    pagesDone: 0,
    processedPages: [],
    pageStats: [],
    startedAt: new Date().toISOString(),
    finishedAt: null,
    stopReason: null,
    lastUpdatedAt: new Date().toISOString(),
    runId: runId,
    searchStartUrl: normalizeSearchPageUrl(location.href),
    lastExport: null
  };

  await setStorage({
    crawlState,
    currentRunRecords: []
  });

  await maybeContinueCrawler();
}

async function stopAutoCrawl() {
  const result = await getStorage(["crawlState"]);
  const crawlState = result.crawlState || {};

  crawlState.running = false;
  crawlState.finished = true;
  crawlState.finishedAt = new Date().toISOString();
  crawlState.stopReason = "Stopped by user";
  crawlState.lastUpdatedAt = new Date().toISOString();

  await setStorage({ crawlState });

  await exportCurrentRun(crawlState);
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "PARSE_JOB_DETAIL") {
    (async () => {
      try {
        const record = parseJobDetailFromPage(message.sourceRecord || null);

        sendResponse({
          success: true,
          record
        });
      } catch (error) {
        sendResponse({
          success: false,
          record: null,
          error: error.message
        });
      }
    })();

    return true;
  }

  if (message && message.type === "COLLECT_JOB_URLS") {
    (async () => {
      try {
        const records = await collectJobRecordsFromAnySupportedPage(
          message.queueItem || null,
          message.runId
        );

        sendResponse({
          success: true,
          records,
          count: records.length
        });
      } catch (error) {
        sendResponse({
          success: false,
          records: [],
          error: error.message
        });
      }
    })();

    return true;
  }

  if (message && message.type === "START_AUTO_CRAWL") {
    (async () => {
      const maxPages = Number(message.maxPages || 50);
      await startAutoCrawl(maxPages);

      sendResponse({
        success: true
      });
    })();

    return true;
  }

  if (message && message.type === "STOP_AUTO_CRAWL") {
    (async () => {
      await stopAutoCrawl();
      sendResponse({
        success: true
      });
    })();

    return true;
  }

  if (message && message.type === "GET_CRAWL_STATUS") {
    (async () => {
      const result = await getStorage([
        "crawlState",
        "collectedJobRecords",
        "currentRunRecords",
        "lastExportInfo"
      ]);

      sendResponse({
        success: true,
        crawlState: result.crawlState || null,
        totalPoolCount: (result.collectedJobRecords || []).length,
        totalRunCount: (result.currentRunRecords || []).length,
        lastExportInfo: result.lastExportInfo || null
      });
    })();

    return true;
  }
});

setInterval(async () => {
  if (location.href !== lastSeenUrl) {
    lastSeenUrl = location.href;
    await sleep(800);
    await maybeContinueCrawler();
  }
}, 1000);

window.addEventListener("load", async () => {
  await sleep(800);
  await maybeContinueCrawler();
});
