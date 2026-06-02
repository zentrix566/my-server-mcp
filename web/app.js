const state = {
  loading: false,
  confidence: null,
};

const elements = {
  targetInput: document.querySelector("#targetInput"),
  spaceInput: document.querySelector("#spaceInput"),
  llmToggle: document.querySelector("#llmToggle"),
  refreshBtn: document.querySelector("#refreshBtn"),
  analyzeBtn: document.querySelector("#analyzeBtn"),
  statusDot: document.querySelector("#statusDot"),
  statusText: document.querySelector("#statusText"),
  generatedAt: document.querySelector("#generatedAt"),
  actionCount: document.querySelector("#actionCount"),
  evidenceCount: document.querySelector("#evidenceCount"),
  actions: document.querySelector("#actions"),
  evidence: document.querySelector("#evidence"),
  llmPanel: document.querySelector("#llmPanel"),
  llmMeta: document.querySelector("#llmMeta"),
  llmSummary: document.querySelector("#llmSummary"),
  llmRootCause: document.querySelector("#llmRootCause"),
  actionTemplate: document.querySelector("#actionTemplate"),
  evidenceTemplate: document.querySelector("#evidenceTemplate"),
};

function percent(value) {
  return Math.round(Number(value || 0));
}

function setStatus(text, tone = "") {
  elements.statusText.textContent = text;
  elements.statusDot.className = `dot ${tone}`.trim();
}

function setLoading(value) {
  state.loading = value;
  elements.refreshBtn.disabled = value;
  elements.analyzeBtn.disabled = value;
}

function formatTime(seconds) {
  if (!seconds) return "";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(seconds * 1000));
}

function renderEmpty(container, text) {
  const node = document.createElement("div");
  node.className = "empty";
  node.textContent = text;
  container.replaceChildren(node);
}

function addCornerTag(card, kind, label, score) {
  const tag = document.createElement("span");
  tag.className = `corner-tag ${kind} ${label || "medium"}`;
  tag.textContent = `${kind === "confidence" ? "置信度" : "相关性"} ${percent(score)}%`;
  card.appendChild(tag);
}

function renderActions(actions) {
  elements.actionCount.textContent = `${actions.length} 条`;
  if (!actions.length) {
    renderEmpty(elements.actions, "暂无处置建议");
    return;
  }

  const nodes = actions.map((action) => {
    const fragment = elements.actionTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".action-card");
    card.classList.add(action.level || "normal");
    fragment.querySelector(".badge").textContent = action.priority || "低";
    fragment.querySelector(".title").textContent = action.title || "未命名建议";
    fragment.querySelector(".eta").textContent = action.eta || "";
    fragment.querySelector(".reason").textContent = action.reason || "";
    fragment.querySelector(".suggestion").textContent = action.suggestion || "";
    if (state.confidence) {
      addCornerTag(card, "confidence", state.confidence.label, state.confidence.score);
    }
    return fragment;
  });

  elements.actions.replaceChildren(...nodes);
}

function renderLlm(llm) {
  if (!llm || !llm.enabled) {
    elements.llmPanel.hidden = true;
    return;
  }

  elements.llmPanel.hidden = false;
  if (llm.success) {
    const confidence = percent(llm.confidence * 100);
    elements.llmMeta.textContent = `${llm.provider || "deepseek"} / ${llm.model || ""} / LLM ${confidence}%`;
    elements.llmSummary.textContent = llm.summary || "LLM 未返回摘要。";
    elements.llmRootCause.textContent = `根因判断：${llm.root_cause || "证据不足，无法确认根因。"}`;
  } else {
    elements.llmMeta.textContent = "已回退到规则分析";
    elements.llmSummary.textContent = "DeepSeek 归因调用失败，当前展示规则分析结果。";
    elements.llmRootCause.textContent = `失败原因：${llm.error || "未知错误"}`;
  }
}

function renderEvidence(evidence) {
  elements.evidenceCount.textContent = `${evidence.length} 条`;
  if (!evidence.length) {
    renderEmpty(elements.evidence, "暂无 MCP 补查证据");
    return;
  }

  const nodes = evidence.map((item) => {
    const fragment = elements.evidenceTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".evidence-card");
    if (!item.success) card.classList.add("failed");
    fragment.querySelector(".tool").textContent = item.tool || "unknown_tool";
    fragment.querySelector(".target").textContent = item.target || "";
    fragment.querySelector(".summary").textContent = item.summary || "";
    fragment.querySelector(".metrics").textContent = JSON.stringify(item.metrics || {}, null, 2);
    if (item.relevance) {
      addCornerTag(card, "relevance", item.relevance.label, item.relevance.score);
    }
    return fragment;
  });

  elements.evidence.replaceChildren(...nodes);
}

async function analyze() {
  if (state.loading) return;
  setLoading(true);
  setStatus("正在调用 MCP 补查并生成建议", "running");

  try {
    const target = elements.targetInput.value.trim();
    const spaceCode = elements.spaceInput.value.trim() || "bkcc__131";
    const useLlm = elements.llmToggle.checked;
    const response = await fetch("/api/analyze/full", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        target: target || null,
        space_code: spaceCode,
        source: "space_list",
        use_llm: useLlm,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    state.confidence = data.confidence || null;
    renderLlm(data.llm);
    renderActions(data.actions || []);
    renderEvidence(data.evidence || []);
    elements.generatedAt.textContent = `生成时间 ${formatTime(data.generated_at)}`;
    setStatus(`已完成 ${data.target || ""} 全量分析`, "done");
  } catch (error) {
    setStatus(`分析失败：${error.message}`, "error");
  } finally {
    setLoading(false);
  }
}

elements.analyzeBtn.addEventListener("click", analyze);
elements.refreshBtn.addEventListener("click", analyze);
window.addEventListener("load", analyze);
