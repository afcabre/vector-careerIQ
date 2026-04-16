import { FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import {
  AIRuntimeConfig,
  AIRun,
  ActiveCV,
  ApplicationArtifact,
  Conversation,
  CulturalFieldPreference,
  CulturalSignal,
  InterviewIteration,
  Opportunity,
  Person,
  PromptConfig,
  PromptConfigVersion,
  RequestTrace,
  SearchProviderConfig,
  SearchProviderStatus,
  SearchResult,
  SemanticEvidence,
  analyzeCulturalFitStream,
  analyzeProfileMatchStream,
  analyzeCulturalFit,
  analyzeProfileMatch,
  createPerson,
  getAiRuntimeConfig,
  getConversation,
  interviewBrief,
  interviewBriefStream,
  getActiveCV,
  getActiveCVText,
  getSession,
  importOpportunityByUrl,
  listOpportunityAiRuns,
  listOpportunityArtifacts,
  listOpportunities,
  listPersons,
  listPromptConfigs,
  listPromptConfigVersions,
  listSearchProviderConfigs,
  listRequestTraces,
  login,
  logout,
  prepareOpportunityStream,
  prepareOpportunity,
  saveOpportunityFromSearch,
  searchOpportunities,
  sendMessage,
  sendMessageStream,
  rollbackPromptConfig as rollbackPromptConfigApi,
  updateAiRuntimeConfig as updateAiRuntimeConfigApi,
  updateSearchProviderConfig as updateSearchProviderConfigApi,
  updatePromptConfig as updatePromptConfigApi,
  updatePerson as updatePersonProfile,
  updateOpportunity,
  uploadCV
} from "./api";

type ViewState = "checking" | "login" | "workspace";
type WorkspacePage = "candidates" | "admin-prompts" | "profile" | "opportunities" | "analysis";
type ParsedWorkspaceRoute = {
  page: WorkspacePage;
  personId: string | null;
};

type ExternalUrlTextProps = {
  url: string | null | undefined;
  noValueText?: string;
};

function parseWorkspacePath(pathname: string): ParsedWorkspaceRoute {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (normalized === "/" || normalized === "/candidates") {
    return { page: "candidates", personId: null };
  }
  if (normalized === "/admin/prompts") {
    return { page: "admin-prompts", personId: null };
  }
  const match = normalized.match(/^\/c\/([^/]+)\/(profile|opportunities|analysis)$/);
  if (!match) {
    return { page: "candidates", personId: null };
  }
  const personId = decodeURIComponent(match[1]);
  const page = match[2] as WorkspacePage;
  return { page, personId };
}

function buildContextPath(personId: string, page: "profile" | "opportunities" | "analysis"): string {
  return `/c/${encodeURIComponent(personId)}/${page}`;
}

function toExternalUrl(url: string | null | undefined): string | null {
  const raw = (url ?? "").trim();
  if (!raw) {
    return null;
  }
  if (/^https?:\/\//i.test(raw)) {
    return raw;
  }
  return `https://${raw}`;
}

function ExternalUrlText({ url, noValueText = "URL no disponible" }: ExternalUrlTextProps) {
  const normalizedUrl = toExternalUrl(url);
  const raw = (url ?? "").trim();
  if (!normalizedUrl || !raw) {
    return <>{noValueText}</>;
  }
  return (
    <a className="inlineLink" href={normalizedUrl} rel="noreferrer" target="_blank">
      {raw}
    </a>
  );
}

function ExpandCollapseIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg aria-hidden="true" className="iconChevron" focusable="false" viewBox="0 0 24 24">
      <path d={expanded ? "M6 14l6-6 6 6" : "M6 10l6 6 6-6"} />
    </svg>
  );
}

function ContextPanelIcon() {
  return (
    <svg aria-hidden="true" className="iconContextPanel" focusable="false" viewBox="0 0 24 24">
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <path d="M8 8h9M8 12h9M8 16h6" />
      <path d="M6 7v10" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg aria-hidden="true" className="iconSpinner" focusable="false" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3a9 9 0 0 1 9 9" />
    </svg>
  );
}

const OPPORTUNITY_STATUSES = [
  "detected",
  "analyzed",
  "prioritized",
  "application_prepared",
  "applied",
  "discarded"
] as const;

const SALARY_CURRENCIES = ["COP", "USD", "EUR"] as const;
const SALARY_PERIODS = [
  { value: "monthly", label: "Mensual" },
  { value: "annual", label: "Anual" }
] as const;

const AI_RUN_ACTION_LABELS: Record<string, string> = {
  analyze_profile_match: "Analizar perfil-vacante",
  analyze_cultural_fit: "Analizar ajuste cultural",
  interview_brief: "Brief de entrevista",
  prepare_guidance_text: "Preparar guia de perfil",
  prepare_cover_letter: "Preparar carta de presentacion",
  prepare_experience_summary: "Preparar resumen de experiencia"
};
const ANALYSIS_CONTEXT_RAIL_COLLAPSE_KEY = "analysis_context_rail_collapsed_v2";
const ACTION_TO_FLOW_KEY: Record<string, string> = {
  analyze_profile_match: "task_analyze_profile_match",
  analyze_cultural_fit: "task_analyze_cultural_fit",
  interview_brief: "task_interview_brief",
  prepare_guidance_text: "task_prepare_guidance",
  prepare_cover_letter: "task_prepare_cover_letter",
  prepare_experience_summary: "task_prepare_experience_summary",
};

type AnalysisResultBlockId =
  | "analysis_profile_match"
  | "analysis_cultural_fit"
  | "analysis_interview_brief"
  | "artifact_guidance_text"
  | "artifact_cover_letter"
  | "artifact_experience_summary";

const ANALYSIS_BLOCK_ORDER: AnalysisResultBlockId[] = [
  "analysis_profile_match",
  "analysis_cultural_fit",
  "analysis_interview_brief"
];

const ARTIFACT_BLOCK_ORDER: AnalysisResultBlockId[] = [
  "artifact_guidance_text",
  "artifact_cover_letter",
  "artifact_experience_summary"
];

const BLOCK_RUN_ACTION_BY_ID: Record<AnalysisResultBlockId, string> = {
  analysis_profile_match: "analyze_profile_match",
  analysis_cultural_fit: "analyze_cultural_fit",
  analysis_interview_brief: "interview_brief",
  artifact_guidance_text: "prepare_guidance_text",
  artifact_cover_letter: "prepare_cover_letter",
  artifact_experience_summary: "prepare_experience_summary"
};

const BLOCK_LABEL_BY_ID: Record<AnalysisResultBlockId, string> = {
  analysis_profile_match: "Alineacion perfil-vacante",
  analysis_cultural_fit: "Fit cultural",
  analysis_interview_brief: "Brief de entrevista",
  artifact_guidance_text: "Guia de perfil",
  artifact_cover_letter: "Carta de presentacion",
  artifact_experience_summary: "Resumen adaptado"
};

const ANALYSIS_MENU_BLOCKS: Array<{
  id: "analysis_profile_match" | "analysis_cultural_fit" | "analysis_interview_brief";
  label: string;
}> = [
  { id: "analysis_profile_match", label: "Perfil-vacante" },
  { id: "analysis_cultural_fit", label: "Fit cultural" },
  { id: "analysis_interview_brief", label: "Entrevista" }
];

const POSTULATION_MENU_BLOCKS: Array<{
  id: "artifact_guidance_text" | "artifact_cover_letter" | "artifact_experience_summary";
  label: string;
}> = [
  { id: "artifact_guidance_text", label: "Guia de perfil" },
  { id: "artifact_cover_letter", label: "Carta de presentacion" },
  { id: "artifact_experience_summary", label: "Resumen adaptado" }
];

const PROMPT_FLOW_LABELS: Record<string, string> = {
  search_jobs_tavily: "Busqueda de vacantes (Tavily)",
  search_culture_tavily: "Fit cultural (Tavily)",
  search_interview_tavily: "Contexto entrevista (Tavily)",
  guardrails_core: "Guardrails core (global)",
  system_identity: "Identidad del sistema (global)",
  task_chat: "Prompt de tarea: Chat",
  task_analyze_profile_match: "Prompt de tarea: Analizar perfil-vacante",
  task_analyze_cultural_fit: "Prompt de tarea: Analizar ajuste cultural",
  task_interview_research_plan: "Prompt de tarea: Plan de investigacion entrevista",
  task_interview_brief: "Prompt de tarea: Brief de entrevista",
  task_prepare_guidance: "Prompt de tarea: Preparar guia de perfil",
  task_prepare_cover_letter: "Prompt de tarea: Preparar carta",
  task_prepare_experience_summary: "Prompt de tarea: Preparar resumen"
};

const PROMPT_FLOW_ORDER: string[] = [
  "search_jobs_tavily",
  "search_culture_tavily",
  "search_interview_tavily",
  "guardrails_core",
  "system_identity",
  "task_chat",
  "task_analyze_profile_match",
  "task_analyze_cultural_fit",
  "task_interview_research_plan",
  "task_interview_brief",
  "task_prepare_guidance",
  "task_prepare_cover_letter",
  "task_prepare_experience_summary"
];
const PROMPT_SOURCE_FLOW_KEYS = new Set([
  "search_jobs_tavily",
  "search_culture_tavily",
  "search_interview_tavily"
]);
const SEARCH_PROVIDER_LABELS: Record<string, string> = {
  adzuna: "Adzuna (RapidAPI)",
  remotive: "Remotive",
  tavily: "Tavily"
};
const AI_RUNTIME_TOP_K_MIN = 4;
const AI_RUNTIME_TOP_K_MAX = 30;
const AI_RUNTIME_INTERVIEW_STEPS_MIN = 3;
const AI_RUNTIME_INTERVIEW_STEPS_MAX = 8;

type PromptConfigDraft = {
  template_text: string;
  target_sources_input: string;
  is_active: boolean;
};

const CULTURAL_FIELDS: Array<{
  id: string;
  label: string;
  options: Array<{ value: string; label: string }>;
}> = [
  {
    id: "work_modality",
    label: "Modalidad de trabajo",
    options: [
      { value: "onsite", label: "Presencial" },
      { value: "hybrid", label: "Hibrido" },
      { value: "remote", label: "Remoto" }
    ]
  },
  {
    id: "schedule_flexibility",
    label: "Flexibilidad de horario",
    options: [
      { value: "fixed_schedule", label: "Horario fijo" },
      { value: "partial_flexibility", label: "Flexibilidad parcial" },
      { value: "high_flexibility", label: "Alta flexibilidad" }
    ]
  },
  {
    id: "work_intensity",
    label: "Intensidad laboral",
    options: [
      { value: "low", label: "Baja" },
      { value: "medium", label: "Media" },
      { value: "high", label: "Alta" }
    ]
  },
  {
    id: "environment_predictability",
    label: "Previsibilidad del entorno",
    options: [
      { value: "very_stable", label: "Muy estable" },
      { value: "moderately_stable", label: "Moderadamente estable" },
      { value: "balanced", label: "Balanceado" },
      { value: "moderately_dynamic", label: "Moderadamente dinamico" },
      { value: "very_dynamic", label: "Muy dinamico" }
    ]
  },
  {
    id: "company_scale",
    label: "Escala de empresa",
    options: [
      { value: "local", label: "Local" },
      { value: "regional", label: "Regional" },
      { value: "multilatina", label: "Multilatina" },
      { value: "multinational", label: "Multinacional" },
      { value: "family_owned", label: "Familiar" }
    ]
  },
  {
    id: "organization_structure_level",
    label: "Nivel de estructuracion",
    options: [
      { value: "low", label: "Baja" },
      { value: "medium_low", label: "Media-baja" },
      { value: "medium", label: "Media" },
      { value: "medium_high", label: "Media-alta" },
      { value: "high", label: "Alta" }
    ]
  },
  {
    id: "organizational_moment",
    label: "Momento organizacional",
    options: [
      { value: "consolidated", label: "Consolidada" },
      { value: "transformation", label: "En transformacion" },
      { value: "high_growth", label: "En crecimiento acelerado" },
      { value: "reorganization", label: "En reorganizacion" }
    ]
  },
  {
    id: "cultural_formality",
    label: "Formalidad cultural",
    options: [
      { value: "very_informal", label: "Muy informal" },
      { value: "more_informal", label: "Mas informal" },
      { value: "intermediate", label: "Intermedia" },
      { value: "more_formal", label: "Mas formal" },
      { value: "very_formal", label: "Muy formal" }
    ]
  }
];

function buildDefaultCulturalPreferences(): Record<string, CulturalFieldPreference> {
  const defaults: Record<string, CulturalFieldPreference> = {};
  for (const field of CULTURAL_FIELDS) {
    defaults[field.id] = {
      enabled: false,
      selected_values: [],
      criticality: "normal"
    };
  }
  return defaults;
}

function getPersonInitials(fullName: string): string {
  return fullName
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "NA";
}

function getArtifactTypeLabel(artifactType: string): string {
  if (artifactType === "cover_letter") {
    return "Carta de presentacion";
  }
  if (artifactType === "experience_summary") {
    return "Resumen de experiencia";
  }
  if (artifactType === "guidance_text") {
    return "Guia de perfil";
  }
  return artifactType;
}

function getOpportunityOriginLabel(sourceType: string): string {
  if (sourceType === "search") {
    return "Busqueda";
  }
  if (sourceType === "manual_url" || sourceType === "manual_text") {
    return "Manual";
  }
  return "Manual";
}

function getOpportunityOriginChipClass(sourceType: string): string {
  if (sourceType === "search") {
    return "metaChip metaChipOrigin metaChipOriginSearch";
  }
  return "metaChip metaChipOrigin metaChipOriginManual";
}

function buildPromptConfigDrafts(
  configs: PromptConfig[]
): Record<string, PromptConfigDraft> {
  const drafts: Record<string, PromptConfigDraft> = {};
  for (const config of configs) {
    drafts[config.flow_key] = {
      template_text: config.template_text,
      target_sources_input: config.target_sources.join("\n"),
      is_active: config.is_active
    };
  }
  return drafts;
}

function getAiRunPreviewText(run: AIRun): string {
  const analysisText = run.result_payload["analysis_text"];
  if (typeof analysisText === "string" && analysisText.trim()) {
    return analysisText;
  }
  const guidanceText = run.result_payload["guidance_text"];
  if (typeof guidanceText === "string" && guidanceText.trim()) {
    return guidanceText;
  }
  const coverLetter = run.result_payload["cover_letter"];
  if (typeof coverLetter === "string" && coverLetter.trim()) {
    return coverLetter;
  }
  const experienceSummary = run.result_payload["experience_summary"];
  if (typeof experienceSummary === "string" && experienceSummary.trim()) {
    return experienceSummary;
  }
  const content = run.result_payload["content"];
  if (typeof content === "string" && content.trim()) {
    return content;
  }
  return "";
}

type PromptBadge = {
  label: string;
  tooltip: string;
};

function getPromptBadgeForFlow(
  resultPayload: Record<string, unknown> | null | undefined,
  flowKey: string
): PromptBadge | null {
  if (!resultPayload || typeof resultPayload !== "object") {
    return null;
  }
  const rawMeta = (resultPayload as Record<string, unknown>)["prompt_meta"];
  if (!rawMeta || typeof rawMeta !== "object") {
    return null;
  }
  const metaRecord = rawMeta as Record<string, Record<string, unknown>>;
  const flowMeta = metaRecord[flowKey];
  if (!flowMeta || typeof flowMeta !== "object") {
    return null;
  }
  const configId = String(flowMeta.config_id ?? "").trim();
  const updatedAt = String(flowMeta.updated_at ?? "").trim();
  const source = String(flowMeta.source ?? "").trim();
  const label = configId ? `Prompt ${configId}` : source ? `Prompt ${source}` : "";
  if (!label) {
    return null;
  }
  const tooltipParts: string[] = [];
  if (configId) {
    tooltipParts.push(`config_id: ${configId}`);
  }
  if (updatedAt) {
    tooltipParts.push(`updated_at: ${updatedAt}`);
  }
  if (source) {
    tooltipParts.push(`source: ${source}`);
  }
  tooltipParts.push(`flow: ${flowKey}`);
  return {
    label,
    tooltip: tooltipParts.join(" · "),
  };
}

function buildContentLinePreview(content: string, maxLines: number, expanded: boolean) {
  const normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const meaningfulLines = normalized
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  const hasOverflow = meaningfulLines.length > maxLines;
  if (expanded) {
    return {
      previewText: normalized,
      truncated: false,
      hasOverflow
    };
  }
  if (meaningfulLines.length <= maxLines) {
    return {
      previewText: meaningfulLines.join("\n"),
      truncated: false,
      hasOverflow
    };
  }
  return {
    previewText: meaningfulLines.slice(0, maxLines).join("\n"),
    truncated: true,
    hasOverflow
  };
}

function renderInlineMarkdown(text: string, keyPrefix: string): Array<string | JSX.Element> {
  const pattern = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*/g;
  const nodes: Array<string | JSX.Element> = [];
  let lastIndex = 0;
  let match = pattern.exec(text);
  let tokenIndex = 0;

  while (match) {
    const start = match.index;
    if (start > lastIndex) {
      nodes.push(text.slice(lastIndex, start));
    }

    if (match[1] && match[2]) {
      const href = toExternalUrl(match[2]);
      if (href) {
        nodes.push(
          <a
            className="inlineLink"
            href={href}
            key={`${keyPrefix}-link-${tokenIndex}`}
            rel="noreferrer"
            target="_blank"
          >
            {match[1]}
          </a>
        );
      } else {
        nodes.push(match[1]);
      }
    } else if (match[3]) {
      nodes.push(<strong key={`${keyPrefix}-strong-${tokenIndex}`}>{match[3]}</strong>);
    } else if (match[4]) {
      nodes.push(<code key={`${keyPrefix}-code-${tokenIndex}`}>{match[4]}</code>);
    } else if (match[5]) {
      nodes.push(<em key={`${keyPrefix}-em-${tokenIndex}`}>{match[5]}</em>);
    }

    lastIndex = pattern.lastIndex;
    tokenIndex += 1;
    match = pattern.exec(text);
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

function splitMarkdownTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((item) => item.trim());
}

function isMarkdownTableDelimiter(line: string): boolean {
  const cells = splitMarkdownTableRow(line);
  if (cells.length === 0) {
    return false;
  }
  return cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function MarkdownContent({ content, className }: { content: string; className?: string }) {
  const lines = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
  const blocks: JSX.Element[] = [];
  let i = 0;
  let blockIndex = 0;

  const isHeading = (line: string) => /^\s{0,3}#{1,6}\s+/.test(line);
  const isUnordered = (line: string) => /^\s*[-*]\s+/.test(line);
  const isOrdered = (line: string) => /^\s*\d+[.)]\s+/.test(line);
  const isTableStart = (idx: number) =>
    idx + 1 < lines.length
    && lines[idx].includes("|")
    && isMarkdownTableDelimiter(lines[idx + 1]);

  while (i < lines.length) {
    const rawLine = lines[i];
    const line = rawLine.trim();
    if (!line) {
      i += 1;
      continue;
    }

    if (isHeading(line)) {
      const level = Math.min(4, Math.max(2, (line.match(/^#{1,6}/)?.[0].length ?? 2)));
      const text = line.replace(/^#{1,6}\s+/, "").trim();
      const headingClass = `mdHeading mdHeading${level}`;
      blocks.push(
        <p className={headingClass} key={`md-h-${blockIndex}`}>
          {renderInlineMarkdown(text, `md-h-${blockIndex}`)}
        </p>
      );
      i += 1;
      blockIndex += 1;
      continue;
    }

    if (isTableStart(i)) {
      const header = splitMarkdownTableRow(lines[i]);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].trim().includes("|")) {
        rows.push(splitMarkdownTableRow(lines[i]));
        i += 1;
      }
      blocks.push(
        <div className="mdTableWrap" key={`md-t-${blockIndex}`}>
          <table className="mdTable">
            <thead>
              <tr>
                {header.map((cell, idx) => (
                  <th key={`md-th-${blockIndex}-${idx}`}>
                    {renderInlineMarkdown(cell, `md-th-${blockIndex}-${idx}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={`md-tr-${blockIndex}-${rowIndex}`}>
                  {row.map((cell, colIndex) => (
                    <td key={`md-td-${blockIndex}-${rowIndex}-${colIndex}`}>
                      {renderInlineMarkdown(cell, `md-td-${blockIndex}-${rowIndex}-${colIndex}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      blockIndex += 1;
      continue;
    }

    if (isUnordered(line)) {
      const items: string[] = [];
      while (i < lines.length && isUnordered(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, "").trim());
        i += 1;
      }
      blocks.push(
        <ul className="mdList" key={`md-ul-${blockIndex}`}>
          {items.map((item, idx) => (
            <li key={`md-ul-${blockIndex}-${idx}`}>
              {renderInlineMarkdown(item, `md-ul-${blockIndex}-${idx}`)}
            </li>
          ))}
        </ul>
      );
      blockIndex += 1;
      continue;
    }

    if (isOrdered(line)) {
      const items: string[] = [];
      while (i < lines.length && isOrdered(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+[.)]\s+/, "").trim());
        i += 1;
      }
      blocks.push(
        <ol className="mdList" key={`md-ol-${blockIndex}`}>
          {items.map((item, idx) => (
            <li key={`md-ol-${blockIndex}-${idx}`}>
              {renderInlineMarkdown(item, `md-ol-${blockIndex}-${idx}`)}
            </li>
          ))}
        </ol>
      );
      blockIndex += 1;
      continue;
    }

    const paragraphLines: string[] = [];
    while (
      i < lines.length
      && lines[i].trim()
      && !isHeading(lines[i].trim())
      && !isUnordered(lines[i].trim())
      && !isOrdered(lines[i].trim())
      && !isTableStart(i)
    ) {
      paragraphLines.push(lines[i].trim());
      i += 1;
    }
    const paragraph = paragraphLines.join(" ");
    blocks.push(
      <p className="mdParagraph" key={`md-p-${blockIndex}`}>
        {renderInlineMarkdown(paragraph, `md-p-${blockIndex}`)}
      </p>
    );
    blockIndex += 1;
  }

  return <div className={className ?? "markdownContent"}>{blocks}</div>;
}

function formatAiRunTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatRequestTraceTimestamp(value: string): string {
  return formatAiRunTimestamp(value);
}

function getTraceStatusLabel(value: string): string {
  const normalized = value.trim().toLowerCase();
  if (normalized === "ok") {
    return "ok";
  }
  if (normalized === "error") {
    return "error";
  }
  if (normalized === "empty") {
    return "sin resultados";
  }
  if (normalized === "skipped") {
    return "omitido";
  }
  return normalized || "n/a";
}

type SearchProviderDiagnostic = {
  statusLabel: string;
  reasonLabel: string;
  rawReason: string;
  httpStatus: number | null;
};

function extractHttpStatus(rawReason: string): number | null {
  const candidates = [
    /\bHTTP Error\s+(\d{3})\b/i,
    /\bstatus(?:\s*code)?[:=\s]+(\d{3})\b/i
  ];
  for (const pattern of candidates) {
    const match = rawReason.match(pattern);
    if (!match) {
      continue;
    }
    const value = Number.parseInt(match[1], 10);
    if (Number.isFinite(value)) {
      return value;
    }
  }
  return null;
}

function getHttpStatusHint(httpStatus: number): string {
  if (httpStatus === 400) {
    return "Solicitud invalida para el proveedor";
  }
  if (httpStatus === 401) {
    return "Credenciales invalidas o ausentes";
  }
  if (httpStatus === 403) {
    return "Acceso denegado por el proveedor";
  }
  if (httpStatus === 404) {
    return "Endpoint no encontrado";
  }
  if (httpStatus === 429) {
    return "Rate limit del proveedor";
  }
  if (httpStatus >= 500) {
    return "Fallo temporal del proveedor";
  }
  return "Error HTTP del proveedor";
}

function buildSearchProviderDiagnostic(status: SearchProviderStatus): SearchProviderDiagnostic {
  const statusLabelMap: Record<SearchProviderStatus["status"], string> = {
    ok: "OK",
    error: "ERROR",
    skipped: "SKIPPED"
  };
  const reasonMap: Record<string, string> = {
    not_executed: "No ejecutado",
    disabled_from_admin: "Deshabilitado en administracion",
    missing_rapidapi_config: "Falta configuracion RapidAPI",
    missing_api_key: "Falta API key",
    no_results: "Sin resultados",
    results_found: "Con resultados",
    provider_error: "Error de proveedor",
    unexpected_error: "Error inesperado"
  };
  const canonicalReason = reasonMap[status.reason];
  const rawReason = (status.reason_detail ?? "").trim() || (canonicalReason ? "" : status.reason);
  const httpStatus =
    typeof status.http_status === "number"
      ? status.http_status
      : extractHttpStatus(rawReason);
  let reasonLabel = canonicalReason ?? "Error de proveedor";
  if (status.status === "error" && httpStatus) {
    reasonLabel = `HTTP ${httpStatus} · ${getHttpStatusHint(httpStatus)}`;
  } else if (status.status !== "error" && canonicalReason) {
    reasonLabel = canonicalReason;
  }
  return {
    statusLabel: statusLabelMap[status.status],
    reasonLabel,
    rawReason,
    httpStatus
  };
}

function normalizeSearchQuery(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function roleToken(role: string): string {
  return `"${role.replace(/"/g, "").trim()}"`;
}

function hasRoleToken(query: string, role: string): boolean {
  const token = roleToken(role);
  if (!token || token === "\"\"") {
    return false;
  }
  const pattern = new RegExp(`(?:^|\\s)${escapeRegex(token)}(?=\\s|$)`, "i");
  return pattern.test(query);
}

function addRoleToken(query: string, role: string): string {
  const token = roleToken(role);
  if (!token || token === "\"\"" || hasRoleToken(query, role)) {
    return normalizeSearchQuery(query);
  }
  return normalizeSearchQuery(`${query} ${token}`);
}

function removeRoleToken(query: string, role: string): string {
  const token = roleToken(role);
  if (!token || token === "\"\"") {
    return normalizeSearchQuery(query);
  }
  const pattern = new RegExp(`(?:^|\\s)${escapeRegex(token)}(?=\\s|$)`, "gi");
  return normalizeSearchQuery(query.replace(pattern, " "));
}

async function copyToClipboard(text: string): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  if (typeof document === "undefined") {
    throw new Error("Clipboard API unavailable");
  }
  const node = document.createElement("textarea");
  node.value = text;
  node.setAttribute("readonly", "true");
  node.style.position = "fixed";
  node.style.opacity = "0";
  document.body.appendChild(node);
  node.select();
  const copied = document.execCommand("copy");
  document.body.removeChild(node);
  if (!copied) {
    throw new Error("Clipboard copy command failed");
  }
}

function appendArtifactDelta(
  current: ApplicationArtifact[],
  personId: string,
  opportunityId: string,
  artifactType: "cover_letter" | "experience_summary",
  delta: string
): ApplicationArtifact[] {
  const now = new Date().toISOString();
  const index = current.findIndex((item) => item.artifact_type === artifactType);
  if (index >= 0) {
    return current.map((item, itemIndex) =>
      itemIndex === index
        ? {
            ...item,
            content: `${item.content}${delta}`,
            updated_at: now
          }
        : item
    );
  }
  return [
    ...current,
    {
      artifact_id: `stream-${artifactType}`,
      person_id: personId,
      opportunity_id: opportunityId,
      artifact_type: artifactType,
      content: delta,
      is_current: true,
      created_at: now,
      updated_at: now
    }
  ];
}

export default function App() {
  const [view, setView] = useState<ViewState>("checking");
  const [currentPath, setCurrentPath] = useState<string>(() => {
    if (typeof window === "undefined") {
      return "/candidates";
    }
    return window.location.pathname || "/candidates";
  });
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [operatorName, setOperatorName] = useState("");
  const [people, setPeople] = useState<Person[]>([]);
  const [selectedPersonId, setSelectedPersonId] = useState<string | null>(null);
  const [promptConfigs, setPromptConfigs] = useState<PromptConfig[]>([]);
  const [promptConfigDrafts, setPromptConfigDrafts] = useState<
    Record<string, PromptConfigDraft>
  >({});
  const [isLoadingPromptConfigs, setIsLoadingPromptConfigs] = useState(false);
  const [promptConfigReloadToken, setPromptConfigReloadToken] = useState(0);
  const [savingPromptFlowKey, setSavingPromptFlowKey] = useState<string | null>(null);
  const [searchProviderConfigs, setSearchProviderConfigs] = useState<SearchProviderConfig[]>([]);
  const [isLoadingSearchProviderConfigs, setIsLoadingSearchProviderConfigs] = useState(false);
  const [savingSearchProviderKey, setSavingSearchProviderKey] = useState<string | null>(null);
  const [aiRuntimeConfig, setAiRuntimeConfig] = useState<AIRuntimeConfig | null>(null);
  const [aiRuntimeTopKAnalysisInput, setAiRuntimeTopKAnalysisInput] = useState("");
  const [aiRuntimeTopKInterviewInput, setAiRuntimeTopKInterviewInput] = useState("");
  const [aiRuntimeCvChunkingStrategyInput, setAiRuntimeCvChunkingStrategyInput] = useState<
    "token_window" | "semantic_sections"
  >("semantic_sections");
  const [aiRuntimeCvMarkdownExtractionModeInput, setAiRuntimeCvMarkdownExtractionModeInput] = useState<
    "heuristic" | "pymupdf4llm"
  >("heuristic");
  const [aiRuntimeInterviewResearchModeInput, setAiRuntimeInterviewResearchModeInput] = useState<
    "guided" | "adaptive"
  >("guided");
  const [aiRuntimeInterviewMaxStepsInput, setAiRuntimeInterviewMaxStepsInput] = useState("");
  const [aiRuntimeTraceTruncationEnabled, setAiRuntimeTraceTruncationEnabled] = useState(true);
  const [isLoadingAiRuntimeConfig, setIsLoadingAiRuntimeConfig] = useState(false);
  const [isSavingAiRuntimeConfig, setIsSavingAiRuntimeConfig] = useState(false);
  const [promptVersionsByFlow, setPromptVersionsByFlow] = useState<
    Record<string, PromptConfigVersion[]>
  >({});
  const [expandedPromptVersions, setExpandedPromptVersions] = useState<
    Record<string, boolean>
  >({});
  const [loadingPromptVersionsFlowKey, setLoadingPromptVersionsFlowKey] = useState<string | null>(
    null
  );
  const [rollingBackPromptFlowKey, setRollingBackPromptFlowKey] = useState<string | null>(null);
  const [newPersonFullName, setNewPersonFullName] = useState("");
  const [newPersonTargetRolesInput, setNewPersonTargetRolesInput] = useState("");
  const [newPersonLocation, setNewPersonLocation] = useState("");
  const [newPersonYearsExperienceInput, setNewPersonYearsExperienceInput] = useState("");
  const [newPersonSkillsInput, setNewPersonSkillsInput] = useState("");
  const [isCreateProfileFormOpen, setIsCreateProfileFormOpen] = useState(false);
  const [isCreatingPerson, setIsCreatingPerson] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [isConversationLoading, setIsConversationLoading] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [streamingAssistantText, setStreamingAssistantText] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchProviderStatus, setSearchProviderStatus] = useState<SearchProviderStatus[]>([]);
  const [selectedSearchResultId, setSelectedSearchResultId] = useState<string | null>(null);
  const [searchWarnings, setSearchWarnings] = useState<string[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [opportunityDiscoveryMode, setOpportunityDiscoveryMode] = useState<"search" | "manual">(
    "manual"
  );
  const [manualUrl, setManualUrl] = useState("");
  const [manualUrlTitle, setManualUrlTitle] = useState("");
  const [manualUrlCompany, setManualUrlCompany] = useState("");
  const [manualUrlLocation, setManualUrlLocation] = useState("");
  const [manualUrlRawText, setManualUrlRawText] = useState("");
  const [isImportingUrl, setIsImportingUrl] = useState(false);
  const [savedOpportunities, setSavedOpportunities] = useState<Opportunity[]>([]);
  const [expandedSavedOpportunityPreview, setExpandedSavedOpportunityPreview] = useState<
    Record<string, boolean>
  >({});
  const [expandedAnalysisOpportunityPreview, setExpandedAnalysisOpportunityPreview] = useState<
    Record<string, boolean>
  >({});
  const [activeCv, setActiveCv] = useState<ActiveCV | null>(null);
  const [activeCvFullText, setActiveCvFullText] = useState("");
  const [selectedCvFile, setSelectedCvFile] = useState<File | null>(null);
  const [isLoadingCv, setIsLoadingCv] = useState(false);
  const [isUploadingCv, setIsUploadingCv] = useState(false);
  const [isLoadingCvFullText, setIsLoadingCvFullText] = useState(false);
  const [isCvUploadFormOpen, setIsCvUploadFormOpen] = useState(false);
  const [isCvPreviewExpanded, setIsCvPreviewExpanded] = useState(false);
  const [isLoadingOpportunities, setIsLoadingOpportunities] = useState(false);
  const [savingResultId, setSavingResultId] = useState<string | null>(null);
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<string | null>(null);
  const [, setAnalysisText] = useState("");
  const [profileAnalysisText, setProfileAnalysisText] = useState("");
  const [cultureAnalysisText, setCultureAnalysisText] = useState("");
  const [interviewBriefText, setInterviewBriefText] = useState("");
  const [culturalConfidence, setCulturalConfidence] = useState("");
  const [culturalWarnings, setCulturalWarnings] = useState<string[]>([]);
  const [culturalSignals, setCulturalSignals] = useState<CulturalSignal[]>([]);
  const [semanticEvidence, setSemanticEvidence] = useState<SemanticEvidence | null>(null);
  const [guidanceText, setGuidanceText] = useState("");
  const [artifacts, setArtifacts] = useState<ApplicationArtifact[]>([]);
  const [aiRuns, setAiRuns] = useState<AIRun[]>([]);
  const [isLoadingAiRuns, setIsLoadingAiRuns] = useState(false);
  const [requestTraces, setRequestTraces] = useState<RequestTrace[]>([]);
  const [isLoadingRequestTraces, setIsLoadingRequestTraces] = useState(false);
  const [focusedRunId, setFocusedRunId] = useState("");
  const [isAnalyzingProfile, setIsAnalyzingProfile] = useState(false);
  const [isAnalyzingCultural, setIsAnalyzingCultural] = useState(false);
  const [isInterviewing, setIsInterviewing] = useState(false);
  const [isPreparing, setIsPreparing] = useState(false);
  const [isLoadingArtifacts, setIsLoadingArtifacts] = useState(false);
  const forceRecomputeAi = false;
  const [resultsPanelTab, setResultsPanelTab] = useState<"analysis" | "artifacts">("analysis");
  const [selectedResultBlockId, setSelectedResultBlockId] = useState<AnalysisResultBlockId | "">(
    ""
  );
  const [runCursorByAction, setRunCursorByAction] = useState<Record<string, number>>({});
  const [expandedResultBlocks, setExpandedResultBlocks] = useState<
    Record<AnalysisResultBlockId, boolean>
  >({
    analysis_profile_match: false,
    analysis_cultural_fit: false,
    analysis_interview_brief: false,
    artifact_guidance_text: false,
    artifact_cover_letter: false,
    artifact_experience_summary: false
  });
  const [, setAnalyzeExecutedByOpportunity] = useState<
    Record<string, boolean>
  >({});
  const [, setArtifactsExecutedByOpportunity] = useState<
    Record<string, boolean>
  >({});
  const [opportunityNotes, setOpportunityNotes] = useState("");
  const [isSavingNotes, setIsSavingNotes] = useState(false);
  const [opportunityStatus, setOpportunityStatus] = useState<string>("detected");
  const [isSavingStatus, setIsSavingStatus] = useState(false);
  const [statusSaveMessage, setStatusSaveMessage] = useState<string | null>(null);
  const [culturePreferencesState, setCulturePreferencesState] = useState<
    Record<string, CulturalFieldPreference>
  >(buildDefaultCulturalPreferences());
  const [culturePreferencesNotes, setCulturePreferencesNotes] = useState("");
  const [isSavingCulturePreferences, setIsSavingCulturePreferences] = useState(false);
  const [profileFullName, setProfileFullName] = useState("");
  const [profileTargetRolesInput, setProfileTargetRolesInput] = useState("");
  const [profileLocation, setProfileLocation] = useState("");
  const [profileYearsExperienceInput, setProfileYearsExperienceInput] = useState("");
  const [profileSkillsInput, setProfileSkillsInput] = useState("");
  const [profileSalaryMinInput, setProfileSalaryMinInput] = useState("");
  const [profileSalaryMaxInput, setProfileSalaryMaxInput] = useState("");
  const [profileSalaryCurrency, setProfileSalaryCurrency] = useState("");
  const [profileSalaryPeriod, setProfileSalaryPeriod] = useState("");
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isChatDrawerOpen, setIsChatDrawerOpen] = useState(false);
  const [isPersonContextMenuOpen, setIsPersonContextMenuOpen] = useState(false);
  const [isContextRailCollapsed, setIsContextRailCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return window.localStorage.getItem(ANALYSIS_CONTEXT_RAIL_COLLAPSE_KEY) === "1";
  });
  const [analysisDetailMountNode, setAnalysisDetailMountNode] = useState<HTMLDivElement | null>(
    null
  );
  const [copiedArtifactKey, setCopiedArtifactKey] = useState<string | null>(null);
  const [copiedOpportunityUrlId, setCopiedOpportunityUrlId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const onPopState = () => {
      setCurrentPath(window.location.pathname || "/candidates");
    };
    window.addEventListener("popstate", onPopState);
    return () => {
      window.removeEventListener("popstate", onPopState);
    };
  }, []);

  useEffect(() => {
    const boot = async () => {
      try {
        const session = await getSession();
        setOperatorName(session.username);
        const items = await listPersons();
        setPeople(items);
        setView("workspace");
        if ((window.location.pathname || "/") === "/login") {
          navigateTo("/candidates", { replace: true });
        }
      } catch {
        setView("login");
        navigateTo("/login", { replace: true });
      }
    };
    void boot();
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(
      ANALYSIS_CONTEXT_RAIL_COLLAPSE_KEY,
      isContextRailCollapsed ? "1" : "0"
    );
  }, [isContextRailCollapsed]);

  useEffect(() => {
    if (view !== "workspace") {
      return;
    }
    const route = parseWorkspacePath(currentPath);
    if (!route.personId) {
      if (currentPath === "/" || currentPath === "/login") {
        navigateTo("/candidates", { replace: true });
      }
      return;
    }
    if (people.length === 0) {
      navigateTo("/candidates", { replace: true });
      return;
    }
    const exists = people.some((item) => item.person_id === route.personId);
    if (!exists) {
      navigateTo(`/c/${people[0].person_id}/profile`, { replace: true });
      return;
    }
    if (selectedPersonId !== route.personId) {
      setSelectedPersonId(route.personId);
    }
  }, [view, currentPath, people, selectedPersonId]);

  useEffect(() => {
    const loadPromptConfigs = async () => {
      if (view !== "workspace") {
        setIsLoadingPromptConfigs(false);
        setIsLoadingSearchProviderConfigs(false);
        setIsLoadingAiRuntimeConfig(false);
        setAiRuntimeConfig(null);
        setAiRuntimeTopKAnalysisInput("");
        setAiRuntimeTopKInterviewInput("");
        setAiRuntimeCvChunkingStrategyInput("semantic_sections");
        setAiRuntimeCvMarkdownExtractionModeInput("heuristic");
        setAiRuntimeInterviewResearchModeInput("guided");
        setAiRuntimeInterviewMaxStepsInput("");
        setSearchProviderConfigs([]);
        setPromptConfigs([]);
        setPromptConfigDrafts({});
        setPromptVersionsByFlow({});
        setExpandedPromptVersions({});
        return;
      }
      setIsLoadingPromptConfigs(true);
      setIsLoadingSearchProviderConfigs(true);
      setIsLoadingAiRuntimeConfig(true);
      setErrorMessage(null);
      try {
        const [items, providerItems, runtimeConfig] = await Promise.all([
          listPromptConfigs(),
          listSearchProviderConfigs(),
          getAiRuntimeConfig()
        ]);
        setPromptConfigs(items);
        setPromptConfigDrafts(buildPromptConfigDrafts(items));
        setSearchProviderConfigs(providerItems);
        setAiRuntimeConfig(runtimeConfig);
        setAiRuntimeTopKAnalysisInput(String(runtimeConfig.top_k_semantic_analysis));
        setAiRuntimeTopKInterviewInput(String(runtimeConfig.top_k_semantic_interview));
        setAiRuntimeCvChunkingStrategyInput(runtimeConfig.cv_chunking_strategy);
        setAiRuntimeCvMarkdownExtractionModeInput(runtimeConfig.cv_markdown_extraction_mode);
        setAiRuntimeInterviewResearchModeInput(runtimeConfig.interview_research_mode);
        setAiRuntimeInterviewMaxStepsInput(String(runtimeConfig.interview_research_max_steps));
        setAiRuntimeTraceTruncationEnabled(runtimeConfig.trace_truncation_enabled);
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "No se pudo cargar configuraciones de administracion";
        setErrorMessage(message);
      } finally {
        setIsLoadingPromptConfigs(false);
        setIsLoadingSearchProviderConfigs(false);
        setIsLoadingAiRuntimeConfig(false);
      }
    };
    void loadPromptConfigs();
  }, [view, promptConfigReloadToken]);

  const selectedPerson =
    people.find((person) => person.person_id === selectedPersonId) ?? null;
  const orderedPromptConfigs = [...promptConfigs].sort((a, b) => {
    const indexA = PROMPT_FLOW_ORDER.indexOf(a.flow_key);
    const indexB = PROMPT_FLOW_ORDER.indexOf(b.flow_key);
    const rankA = indexA >= 0 ? indexA : Number.MAX_SAFE_INTEGER;
    const rankB = indexB >= 0 ? indexB : Number.MAX_SAFE_INTEGER;
    return rankA - rankB;
  });
  const searchProviderOrder: Array<SearchProviderConfig["provider_key"]> = [
    "tavily",
    "adzuna",
    "remotive"
  ];
  const orderedSearchProviderConfigs = [...searchProviderConfigs].sort((a, b) => {
    const indexA = searchProviderOrder.indexOf(a.provider_key);
    const indexB = searchProviderOrder.indexOf(b.provider_key);
    return indexA - indexB;
  });
  const parsedRoute = parseWorkspacePath(currentPath);
  const showCandidatesPage = parsedRoute.page === "candidates";
  const showAdminPromptsPage = parsedRoute.page === "admin-prompts";
  const showProfilePage = parsedRoute.page === "profile";
  const showOpportunitiesPage = parsedRoute.page === "opportunities";
  const showAnalysisPage = parsedRoute.page === "analysis";
  const showContextualSidebar = showProfilePage || showOpportunitiesPage || showAnalysisPage;
  const showConversationSection = showContextualSidebar;
  const shellClassName =
    showConversationSection && isChatDrawerOpen ? "shell shellWithChatDrawer" : "shell";
  const currentPageLabel = showCandidatesPage
    ? "Seleccion de candidato"
    : showAdminPromptsPage
      ? "Administracion global"
      : showProfilePage
        ? "Perfil"
        : showOpportunitiesPage
          ? "Vacantes"
          : "Análisis";
  const currentPageTitle = showCandidatesPage
    ? "Selecciona un perfil para abrir su contexto."
    : showAdminPromptsPage
      ? "Ajusta prompts globales, proveedores y control de retrieval semantico."
      : showProfilePage
        ? "Gestiona perfil y CV del perfil activo."
        : showOpportunitiesPage
          ? "Busca, revisa e importa oportunidades para el contexto activo."
          : "Analiza el perfil y prepara entregables por oportunidad.";
  const currentPageLede = showContextualSidebar
    ? showProfilePage
      ? null
      : "Usa las pestañas para gestionar perfil, busqueda y análisis."
    : "Este flujo separa acceso del tutor y contexto del perfil consultado.";
  const searchRoleKeywords = Array.from(
    new Set(
      (selectedPerson?.target_roles ?? [])
        .map((item) => item.trim())
        .filter(Boolean)
    )
  );
  const selectedSearchRoleCount = searchRoleKeywords.filter((role) =>
    hasRoleToken(searchQuery, role)
  ).length;
  const cvPreviewLineLimit = 8;
  const cvPreviewText = (
    activeCv?.structured_markdown_preview
    || activeCv?.extracted_text_preview
    || ""
  ).trim();
  const cvExpandedText = (activeCvFullText || cvPreviewText).trim();
  const cvPreviewLines = cvPreviewText ? cvPreviewText.split(/\r?\n/) : [];
  const cvPreviewShortText = cvPreviewLines
    .slice(0, cvPreviewLineLimit)
    .join("\n")
    .trim();
  const hasMoreCvPreview =
    cvPreviewLines.length > cvPreviewLineLimit ||
    cvPreviewText.length > cvPreviewShortText.length ||
    (activeCv?.text_length ?? 0) > cvPreviewText.length;

  useEffect(() => {
    setIsPersonContextMenuOpen(false);
  }, [currentPath, selectedPersonId]);

  useEffect(() => {
    setActiveCvFullText("");
    if (!activeCv) {
      setIsCvUploadFormOpen(true);
      setIsCvPreviewExpanded(false);
      return;
    }
    setIsCvUploadFormOpen(false);
    setIsCvPreviewExpanded(false);
  }, [activeCv?.cv_id]);

  function navigateTo(path: string, options?: { replace?: boolean }) {
    if (typeof window === "undefined") {
      setCurrentPath(path);
      return;
    }
    const replace = Boolean(options?.replace);
    if (window.location.pathname === path) {
      setCurrentPath(path);
      return;
    }
    if (replace) {
      window.history.replaceState({}, "", path);
    } else {
      window.history.pushState({}, "", path);
    }
    setCurrentPath(path);
  }

  useEffect(() => {
    const loadConversation = async () => {
      if (!selectedPersonId || view !== "workspace") {
        setConversation(null);
        setStreamingAssistantText("");
        return;
      }
      setIsConversationLoading(true);
      setErrorMessage(null);
      try {
        const payload = await getConversation(selectedPersonId);
        setConversation(payload);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "No se pudo cargar la conversacion";
        setErrorMessage(message);
      } finally {
        setIsConversationLoading(false);
      }
    };
    void loadConversation();
  }, [selectedPersonId, view]);

  useEffect(() => {
    const loadOpportunities = async () => {
      if (!selectedPersonId || view !== "workspace") {
        setSavedOpportunities([]);
        setSelectedOpportunityId(null);
        setAnalysisText("");
        setProfileAnalysisText("");
        setCultureAnalysisText("");
        setCulturalConfidence("");
        setCulturalWarnings([]);
        setCulturalSignals([]);
        setSemanticEvidence(null);
        setGuidanceText("");
        setArtifacts([]);
        setAiRuns([]);
        setRequestTraces([]);
        setFocusedRunId("");
        setSelectedResultBlockId("");
        setRunCursorByAction({});
      setOpportunityNotes("");
      setOpportunityStatus("detected");
        setAnalyzeExecutedByOpportunity({});
        setArtifactsExecutedByOpportunity({});
        setResultsPanelTab("analysis");
        return;
      }
      setIsLoadingOpportunities(true);
      setErrorMessage(null);
      try {
        const items = await listOpportunities(selectedPersonId);
        setSavedOpportunities(items);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "No se pudieron cargar oportunidades";
        setErrorMessage(message);
      } finally {
        setIsLoadingOpportunities(false);
      }
    };
    void loadOpportunities();
  }, [selectedPersonId, view]);

  useEffect(() => {
    const loadActiveCv = async () => {
      if (!selectedPersonId || view !== "workspace") {
        setActiveCv(null);
        setActiveCvFullText("");
        setSelectedCvFile(null);
        return;
      }
      setIsLoadingCv(true);
      setErrorMessage(null);
      try {
        const item = await getActiveCV(selectedPersonId);
        setActiveCv(item);
        setActiveCvFullText("");
      } catch (error) {
        const message = error instanceof Error ? error.message : "No se pudo cargar el CV activo";
        setErrorMessage(message);
      } finally {
        setIsLoadingCv(false);
      }
    };
    void loadActiveCv();
  }, [selectedPersonId, view]);

  useEffect(() => {
    if (showConversationSection && selectedPersonId) {
      return;
    }
    setIsChatDrawerOpen(false);
  }, [showConversationSection, selectedPersonId]);

  const selectedOpportunity =
    savedOpportunities.find((item) => item.opportunity_id === selectedOpportunityId) ?? null;

  function asStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) {
      return [];
    }
    return value.map((item) => String(item)).filter((item) => item.trim().length > 0);
  }

  function asCulturalSignals(value: unknown): CulturalSignal[] {
    if (!Array.isArray(value)) {
      return [];
    }
    const signals: CulturalSignal[] = [];
    for (const item of value) {
      if (!item || typeof item !== "object") {
        continue;
      }
      const raw = item as Record<string, unknown>;
      signals.push({
        source_provider: String(raw.source_provider ?? ""),
        source_url: String(raw.source_url ?? ""),
        title: String(raw.title ?? ""),
        snippet: String(raw.snippet ?? ""),
        captured_at: String(raw.captured_at ?? "")
      });
    }
    return signals;
  }

  function asInterviewIterations(value: unknown): InterviewIteration[] {
    if (!Array.isArray(value)) {
      return [];
    }
    const items: InterviewIteration[] = [];
    for (const item of value) {
      if (!item || typeof item !== "object") {
        continue;
      }
      const raw = item as Record<string, unknown>;
      const topUrlsRaw = raw.top_urls;
      items.push({
        step_order: Number.parseInt(String(raw.step_order ?? 0), 10) || 0,
        topic_key: String(raw.topic_key ?? ""),
        topic_label: String(raw.topic_label ?? ""),
        query: String(raw.query ?? ""),
        status: String(raw.status ?? ""),
        results_count: Number.parseInt(String(raw.results_count ?? 0), 10) || 0,
        top_urls: Array.isArray(topUrlsRaw)
          ? topUrlsRaw.map((value) => String(value)).filter((value) => value.trim().length > 0)
          : [],
        warning: String(raw.warning ?? "")
      });
    }
    return items;
  }

  useEffect(() => {
    if (
      !selectedOpportunityId ||
      isAnalyzingProfile ||
      isAnalyzingCultural ||
      isInterviewing ||
      isPreparing
    ) {
      return;
    }

    const byAction = new Map<string, AIRun>();
    for (const run of aiRuns) {
      if (!byAction.has(run.action_key) || run.is_current) {
        byAction.set(run.action_key, run);
      }
    }

    const profileRun = byAction.get("analyze_profile_match");
    const culturalRun = byAction.get("analyze_cultural_fit");
    const interviewRun = byAction.get("interview_brief");
    const guidanceRun = byAction.get("prepare_guidance_text");
    const profilePayload = (profileRun?.result_payload ?? {}) as Record<string, unknown>;
    const culturalPayload = (culturalRun?.result_payload ?? {}) as Record<string, unknown>;
    const guidancePayload = (guidanceRun?.result_payload ?? {}) as Record<string, unknown>;
    const interviewPayload = (interviewRun?.result_payload ?? {}) as Record<string, unknown>;

    setProfileAnalysisText(String(profilePayload.analysis_text ?? "").trim());
    setCultureAnalysisText(String(culturalPayload.analysis_text ?? "").trim());
    setInterviewBriefText(String(interviewPayload.analysis_text ?? "").trim());
    setCulturalConfidence(String(culturalPayload.cultural_confidence ?? "").trim());
    setCulturalWarnings(asStringArray(culturalPayload.cultural_warnings));
    setCulturalSignals(asCulturalSignals(culturalPayload.cultural_signals));

    const profileEvidence = profilePayload.semantic_evidence;
    const interviewEvidence = interviewPayload.semantic_evidence;
    const guidanceEvidence = guidancePayload.semantic_evidence;
    if (profileEvidence && typeof profileEvidence === "object") {
      setSemanticEvidence(profileEvidence as SemanticEvidence);
    } else if (interviewEvidence && typeof interviewEvidence === "object") {
      setSemanticEvidence(interviewEvidence as SemanticEvidence);
    } else if (guidanceEvidence && typeof guidanceEvidence === "object") {
      setSemanticEvidence(guidanceEvidence as SemanticEvidence);
    }

    const guidanceText = String(guidancePayload.guidance_text ?? guidancePayload.content ?? "").trim();
    if (guidanceText) {
      setGuidanceText(guidanceText);
    }
  }, [
    aiRuns,
    selectedOpportunityId,
    isAnalyzingProfile,
    isAnalyzingCultural,
    isInterviewing,
    isPreparing
  ]);
  const aiRunsById = new Map(aiRuns.map((item) => [item.run_id, item] as const));
  const aiRunsByAction = new Map<string, AIRun[]>();
  for (const run of aiRuns) {
    const actionRuns = aiRunsByAction.get(run.action_key) ?? [];
    actionRuns.push(run);
    aiRunsByAction.set(run.action_key, actionRuns);
  }
  for (const actionRuns of aiRunsByAction.values()) {
    actionRuns.sort((left, right) => {
      const leftCurrent = left.is_current ? 1 : 0;
      const rightCurrent = right.is_current ? 1 : 0;
      if (leftCurrent !== rightCurrent) {
        return rightCurrent - leftCurrent;
      }
      const updated = right.updated_at.localeCompare(left.updated_at);
      if (updated !== 0) {
        return updated;
      }
      return right.created_at.localeCompare(left.created_at);
    });
  }

  const getRunsForBlock = (blockId: AnalysisResultBlockId) =>
    aiRunsByAction.get(BLOCK_RUN_ACTION_BY_ID[blockId]) ?? [];

  const getSelectedRunForBlock = (blockId: AnalysisResultBlockId): AIRun | null => {
    const runs = getRunsForBlock(blockId);
    if (runs.length === 0) {
      return null;
    }
    const cursor = runCursorByAction[BLOCK_RUN_ACTION_BY_ID[blockId]] ?? 0;
    const safeCursor = Math.min(Math.max(cursor, 0), runs.length - 1);
    return runs[safeCursor] ?? null;
  };

  const selectedBlockRun =
    selectedResultBlockId ? getSelectedRunForBlock(selectedResultBlockId) : null;
  const focusedRun = selectedBlockRun ?? (focusedRunId ? aiRunsById.get(focusedRunId) ?? null : null);
  const focusedRunRequestTraces = [...requestTraces].sort((left, right) => {
    const leftStep = Number.isFinite(left.step_order) ? left.step_order : 0;
    const rightStep = Number.isFinite(right.step_order) ? right.step_order : 0;
    if (leftStep > 0 || rightStep > 0) {
      if (leftStep === 0) {
        return 1;
      }
      if (rightStep === 0) {
        return -1;
      }
      if (leftStep !== rightStep) {
        return leftStep - rightStep;
      }
    }
    return left.created_at.localeCompare(right.created_at);
  });

  useEffect(() => {
    if (!showAnalysisPage) {
      return;
    }
    if (!selectedPersonId || !selectedOpportunityId) {
      setAiRuns([]);
      return;
    }
    void refreshAiRunsFor(selectedPersonId, selectedOpportunityId);
  }, [selectedPersonId, selectedOpportunityId, showAnalysisPage]);

  useEffect(() => {
    if (!showAnalysisPage) {
      return;
    }
    if (!selectedPersonId || !selectedOpportunityId) {
      setArtifacts([]);
      setGuidanceText("");
      return;
    }
    void refreshArtifacts(selectedOpportunityId);
  }, [selectedPersonId, selectedOpportunityId, showAnalysisPage]);

  useEffect(() => {
    if (!selectedOpportunityId) {
      setRunCursorByAction({});
      setSelectedResultBlockId("");
      setFocusedRunId("");
      setRequestTraces([]);
      return;
    }
    setExpandedResultBlocks({
      analysis_profile_match: false,
      analysis_cultural_fit: false,
      analysis_interview_brief: false,
      artifact_guidance_text: false,
      artifact_cover_letter: false,
      artifact_experience_summary: false
    });
  }, [selectedOpportunityId]);

  useEffect(() => {
    setRunCursorByAction((current) => {
      const next = { ...current };
      for (const blockId of [...ANALYSIS_BLOCK_ORDER, ...ARTIFACT_BLOCK_ORDER]) {
        const actionKey = BLOCK_RUN_ACTION_BY_ID[blockId];
        const runs = getRunsForBlock(blockId);
        if (runs.length === 0) {
          next[actionKey] = 0;
          continue;
        }
        const currentCursor = current[actionKey] ?? 0;
        next[actionKey] = Math.min(Math.max(currentCursor, 0), runs.length - 1);
      }
      return next;
    });
  }, [aiRuns, selectedOpportunityId]);

  useEffect(() => {
    if (!selectedOpportunityId) {
      return;
    }
    const blockOrder = resultsPanelTab === "analysis" ? ANALYSIS_BLOCK_ORDER : ARTIFACT_BLOCK_ORDER;
    setSelectedResultBlockId((current) => {
      if (current && blockOrder.includes(current)) {
        return current;
      }
      const firstWithRun = blockOrder.find((blockId) => getRunsForBlock(blockId).length > 0);
      return firstWithRun ?? blockOrder[0];
    });
  }, [resultsPanelTab, selectedOpportunityId, aiRuns]);

  useEffect(() => {
    if (!selectedOpportunityId || !selectedResultBlockId) {
      setFocusedRunId("");
      return;
    }
    const selectedRun = getSelectedRunForBlock(selectedResultBlockId);
    setFocusedRunId(selectedRun?.run_id ?? "");
  }, [selectedOpportunityId, selectedResultBlockId, aiRuns, runCursorByAction]);

  useEffect(() => {
    if (!showAnalysisPage) {
      return;
    }
    if (!selectedPersonId || !selectedOpportunityId || !focusedRunId) {
      setRequestTraces([]);
      return;
    }
    void refreshRequestTracesFor(selectedPersonId, selectedOpportunityId, focusedRunId);
  }, [selectedPersonId, selectedOpportunityId, focusedRunId, showAnalysisPage]);

  useEffect(() => {
    if (!showAnalysisPage || !selectedOpportunityId || typeof window === "undefined") {
      return;
    }
    const selector = `[data-analysis-row-id="${CSS.escape(selectedOpportunityId)}"]`;
    const target = document.querySelector(selector);
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const prefersReducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    window.requestAnimationFrame(() => {
      target.scrollIntoView({
        behavior: prefersReducedMotion ? "auto" : "smooth",
        block: "start",
      });
    });
  }, [selectedOpportunityId, showAnalysisPage]);

  useEffect(() => {
    setSelectedOpportunityId(null);
    setFocusedRunId("");
    setSelectedResultBlockId("");
    setRunCursorByAction({});
    setAiRuns([]);
    setRequestTraces([]);
  }, [selectedPersonId]);

  useEffect(() => {
    setSearchQuery("");
    setSearchResults([]);
    setSearchProviderStatus([]);
    setSelectedSearchResultId(null);
    setSearchWarnings([]);
  }, [selectedPersonId]);

  useEffect(() => {
    setOpportunityDiscoveryMode("search");
  }, [selectedPersonId]);

  useEffect(() => {
    setExpandedSavedOpportunityPreview({});
  }, [selectedPersonId]);

  useEffect(() => {
    if (!selectedSearchResultId) {
      return;
    }
    if (searchResults.some((item) => item.search_result_id === selectedSearchResultId)) {
      return;
    }
    setSelectedSearchResultId(null);
  }, [searchResults, selectedSearchResultId]);

  useEffect(() => {
    setOpportunityNotes(selectedOpportunity?.notes ?? "");
  }, [selectedOpportunity?.opportunity_id, selectedOpportunity?.notes]);

  useEffect(() => {
    setOpportunityStatus(selectedOpportunity?.status ?? "detected");
    setStatusSaveMessage(null);
  }, [selectedOpportunity?.opportunity_id, selectedOpportunity?.status]);

  useEffect(() => {
    if (!statusSaveMessage) {
      return;
    }
    const timeoutId = window.setTimeout(() => {
      setStatusSaveMessage(null);
    }, 2600);
    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [statusSaveMessage]);

  useEffect(() => {
    if (!selectedPerson) {
      setProfileFullName("");
      setProfileTargetRolesInput("");
      setProfileLocation("");
      setProfileYearsExperienceInput("");
      setProfileSkillsInput("");
      setProfileSalaryMinInput("");
      setProfileSalaryMaxInput("");
      setProfileSalaryCurrency("");
      setProfileSalaryPeriod("");
      setCulturePreferencesState(buildDefaultCulturalPreferences());
      setCulturePreferencesNotes("");
      return;
    }
    setProfileFullName(selectedPerson.full_name ?? "");
    setProfileTargetRolesInput((selectedPerson.target_roles ?? []).join(", "));
    setProfileLocation(selectedPerson.location ?? "");
    setProfileYearsExperienceInput(String(selectedPerson.years_experience ?? 0));
    setProfileSkillsInput((selectedPerson.skills ?? []).join(", "));
    setProfileSalaryMinInput(
      selectedPerson.salary_expectation_min !== null
        ? String(selectedPerson.salary_expectation_min)
        : ""
    );
    setProfileSalaryMaxInput(
      selectedPerson.salary_expectation_max !== null
        ? String(selectedPerson.salary_expectation_max)
        : ""
    );
    setProfileSalaryCurrency(selectedPerson.salary_currency ?? "");
    setProfileSalaryPeriod(selectedPerson.salary_period ?? "");

    const defaults = buildDefaultCulturalPreferences();
    const incoming = selectedPerson.cultural_fit_preferences ?? {};
    const nextState: Record<string, CulturalFieldPreference> = { ...defaults };

    for (const field of CULTURAL_FIELDS) {
      const raw = incoming[field.id];
      if (!raw) {
        continue;
      }
      const allowedOptions = new Set(field.options.map((item) => item.value));
      const selectedValues = (raw.selected_values ?? []).filter((item) =>
        allowedOptions.has(item)
      );
      nextState[field.id] = {
        enabled: selectedValues.length > 0,
        selected_values: selectedValues,
        criticality:
          raw.criticality === "high_penalty" || raw.criticality === "non_negotiable"
            ? raw.criticality
            : "normal"
      };
    }

    setCulturePreferencesState(nextState);
    setCulturePreferencesNotes(selectedPerson.culture_preferences_notes ?? "");
  }, [
    selectedPerson?.person_id,
    selectedPerson?.full_name,
    selectedPerson?.target_roles,
    selectedPerson?.location,
    selectedPerson?.years_experience,
    selectedPerson?.skills,
    selectedPerson?.salary_expectation_min,
    selectedPerson?.salary_expectation_max,
    selectedPerson?.salary_currency,
    selectedPerson?.salary_period,
    selectedPerson?.cultural_fit_preferences,
    selectedPerson?.culture_preferences_notes
  ]);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      const session = await login(username, password);
      setOperatorName(session.username);
      setPassword("");
      const items = await listPersons();
      setPeople(items);
      if (items.length > 0) {
        setSelectedPersonId(items[0].person_id);
      }
      setView("workspace");
      navigateTo("/candidates", { replace: true });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo iniciar sesion";
      setErrorMessage(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogout() {
    setErrorMessage(null);
    try {
      await logout();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo cerrar sesion";
      setErrorMessage(message);
      return;
    }
    setView("login");
    navigateTo("/login", { replace: true });
    setOperatorName("");
    setPassword("");
    setSelectedPersonId(null);
    setPeople([]);
    setSearchProviderConfigs([]);
    setPromptConfigs([]);
    setPromptConfigDrafts({});
    setPromptVersionsByFlow({});
    setExpandedPromptVersions({});
    setNewPersonFullName("");
    setNewPersonTargetRolesInput("");
    setNewPersonLocation("");
    setNewPersonYearsExperienceInput("");
    setNewPersonSkillsInput("");
    setConversation(null);
    setStreamingAssistantText("");
    setChatInput("");
    setAnalysisText("");
    setCulturalConfidence("");
    setCulturalWarnings([]);
    setCulturalSignals([]);
    setSemanticEvidence(null);
    setAiRuns([]);
    setRequestTraces([]);
    setFocusedRunId("");
    setSelectedResultBlockId("");
    setRunCursorByAction({});
    setActiveCv(null);
    setActiveCvFullText("");
    setSelectedCvFile(null);
  }

  async function handleCreatePerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isCreatingPerson) {
      return;
    }

    const fullName = newPersonFullName.trim();
    const location = newPersonLocation.trim();
    const yearsExperience = Number.parseInt(newPersonYearsExperienceInput.trim(), 10);
    const targetRoles = newPersonTargetRolesInput
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);
    const skills = newPersonSkillsInput
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);

    if (!fullName || !location || targetRoles.length === 0 || skills.length === 0) {
      setErrorMessage(
        "Nuevo perfil incompleto: nombre, ubicacion, roles y skills son obligatorios."
      );
      return;
    }
    if (!Number.isFinite(yearsExperience) || yearsExperience < 0 || yearsExperience > 80) {
      setErrorMessage("Años de experiencia debe estar entre 0 y 80.");
      return;
    }

    setIsCreatingPerson(true);
    setErrorMessage(null);
    try {
      const created = await createPerson({
        full_name: fullName,
        target_roles: targetRoles,
        location,
        years_experience: yearsExperience,
        skills
      });
      const items = await listPersons();
      setPeople(items);
      setSelectedPersonId(created.person_id);
      navigateTo(buildContextPath(created.person_id, "profile"));
      setNewPersonFullName("");
      setNewPersonTargetRolesInput("");
      setNewPersonLocation("");
      setNewPersonYearsExperienceInput("");
      setNewPersonSkillsInput("");
      setIsCreateProfileFormOpen(false);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo crear el nuevo perfil";
      setErrorMessage(message);
    } finally {
      setIsCreatingPerson(false);
    }
  }

  function handlePromptDraftChange(
    flowKey: string,
    patch: Partial<PromptConfigDraft>
  ) {
    setPromptConfigDrafts((current) => {
      const currentDraft = current[flowKey] ?? {
        template_text: "",
        target_sources_input: "",
        is_active: true
      };
      return {
        ...current,
        [flowKey]: {
          ...currentDraft,
          ...patch
        }
      };
    });
  }

  async function handleSavePromptConfig(flowKey: string) {
    const draft = promptConfigDrafts[flowKey];
    if (!draft || savingPromptFlowKey) {
      return;
    }

    const templateText = draft.template_text.trim();
    const targetSources = draft.target_sources_input
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);

    if (!templateText) {
      setErrorMessage("La plantilla de prompt no puede estar vacia.");
      return;
    }

    setSavingPromptFlowKey(flowKey);
    setErrorMessage(null);
    try {
      const updated = await updatePromptConfigApi(flowKey, {
        template_text: templateText,
        target_sources: PROMPT_SOURCE_FLOW_KEYS.has(flowKey) ? targetSources : [],
        is_active: draft.is_active
      });
      setPromptConfigs((current) =>
        current.map((item) => (item.flow_key === updated.flow_key ? updated : item))
      );
      setPromptConfigDrafts((current) => ({
        ...current,
        [flowKey]: {
          template_text: updated.template_text,
          target_sources_input: updated.target_sources.join("\n"),
          is_active: updated.is_active
        }
      }));
      if (expandedPromptVersions[flowKey]) {
        await loadPromptVersions(flowKey, true);
      }
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "No se pudo guardar la configuracion del prompt";
      setErrorMessage(message);
    } finally {
      setSavingPromptFlowKey(null);
    }
  }

  async function handleToggleSearchProvider(
    providerKey: "adzuna" | "remotive" | "tavily",
    isEnabled: boolean
  ) {
    if (savingSearchProviderKey) {
      return;
    }
    setSavingSearchProviderKey(providerKey);
    setErrorMessage(null);
    try {
      const updated = await updateSearchProviderConfigApi(providerKey, isEnabled);
      setSearchProviderConfigs((current) =>
        current.map((item) => (item.provider_key === updated.provider_key ? updated : item))
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo actualizar el proveedor";
      setErrorMessage(message);
    } finally {
      setSavingSearchProviderKey((current) => (current === providerKey ? null : current));
    }
  }

  async function handleSaveAiRuntimeConfig() {
    if (isSavingAiRuntimeConfig) {
      return;
    }

    const parsedAnalysis = Number.parseInt(aiRuntimeTopKAnalysisInput, 10);
    const parsedInterview = Number.parseInt(aiRuntimeTopKInterviewInput, 10);
    const parsedInterviewSteps = Number.parseInt(aiRuntimeInterviewMaxStepsInput, 10);

    if (
      !Number.isFinite(parsedAnalysis) ||
      parsedAnalysis < AI_RUNTIME_TOP_K_MIN ||
      parsedAnalysis > AI_RUNTIME_TOP_K_MAX
    ) {
      setErrorMessage(
        `top_k análisis debe estar entre ${AI_RUNTIME_TOP_K_MIN} y ${AI_RUNTIME_TOP_K_MAX}.`
      );
      return;
    }
    if (
      !Number.isFinite(parsedInterview) ||
      parsedInterview < AI_RUNTIME_TOP_K_MIN ||
      parsedInterview > AI_RUNTIME_TOP_K_MAX
    ) {
      setErrorMessage(
        `top_k entrevista debe estar entre ${AI_RUNTIME_TOP_K_MIN} y ${AI_RUNTIME_TOP_K_MAX}.`
      );
      return;
    }
    if (
      !Number.isFinite(parsedInterviewSteps) ||
      parsedInterviewSteps < AI_RUNTIME_INTERVIEW_STEPS_MIN ||
      parsedInterviewSteps > AI_RUNTIME_INTERVIEW_STEPS_MAX
    ) {
      setErrorMessage(
        "max steps de entrevista debe estar entre "
          + `${AI_RUNTIME_INTERVIEW_STEPS_MIN} y ${AI_RUNTIME_INTERVIEW_STEPS_MAX}.`
      );
      return;
    }
    if (
      aiRuntimeCvChunkingStrategyInput !== "token_window"
      && aiRuntimeCvChunkingStrategyInput !== "semantic_sections"
    ) {
      setErrorMessage("Estrategia de chunking CV invalida.");
      return;
    }
    if (
      aiRuntimeCvMarkdownExtractionModeInput !== "heuristic"
      && aiRuntimeCvMarkdownExtractionModeInput !== "pymupdf4llm"
    ) {
      setErrorMessage("Modo de extraccion Markdown de CV invalido.");
      return;
    }
    if (
      aiRuntimeInterviewResearchModeInput !== "guided"
      && aiRuntimeInterviewResearchModeInput !== "adaptive"
    ) {
      setErrorMessage("Modo de investigacion de entrevista invalido.");
      return;
    }

    setIsSavingAiRuntimeConfig(true);
    setErrorMessage(null);
    try {
      const updated = await updateAiRuntimeConfigApi({
        top_k_semantic_analysis: parsedAnalysis,
        top_k_semantic_interview: parsedInterview,
        cv_chunking_strategy: aiRuntimeCvChunkingStrategyInput,
        cv_markdown_extraction_mode: aiRuntimeCvMarkdownExtractionModeInput,
        interview_research_mode: aiRuntimeInterviewResearchModeInput,
        interview_research_max_steps: parsedInterviewSteps,
        trace_truncation_enabled: aiRuntimeTraceTruncationEnabled,
      });
      setAiRuntimeConfig(updated);
      setAiRuntimeTopKAnalysisInput(String(updated.top_k_semantic_analysis));
      setAiRuntimeTopKInterviewInput(String(updated.top_k_semantic_interview));
      setAiRuntimeCvChunkingStrategyInput(updated.cv_chunking_strategy);
      setAiRuntimeCvMarkdownExtractionModeInput(updated.cv_markdown_extraction_mode);
      setAiRuntimeInterviewResearchModeInput(updated.interview_research_mode);
      setAiRuntimeInterviewMaxStepsInput(String(updated.interview_research_max_steps));
      setAiRuntimeTraceTruncationEnabled(updated.trace_truncation_enabled);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo guardar configuracion IA";
      setErrorMessage(message);
    } finally {
      setIsSavingAiRuntimeConfig(false);
    }
  }

  async function loadPromptVersions(flowKey: string, force = false) {
    if (!force && promptVersionsByFlow[flowKey]) {
      return;
    }
    setLoadingPromptVersionsFlowKey(flowKey);
    try {
      const items = await listPromptConfigVersions(flowKey, 20);
      setPromptVersionsByFlow((current) => ({
        ...current,
        [flowKey]: items
      }));
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo cargar historial de versiones";
      setErrorMessage(message);
    } finally {
      setLoadingPromptVersionsFlowKey((current) =>
        current === flowKey ? null : current
      );
    }
  }

  function handleTogglePromptVersions(flowKey: string) {
    setExpandedPromptVersions((current) => {
      const next = !current[flowKey];
      const updated = {
        ...current,
        [flowKey]: next
      };
      if (next) {
        void loadPromptVersions(flowKey);
      }
      return updated;
    });
  }

  async function handleRollbackPromptConfig(flowKey: string, versionId: string) {
    if (!versionId.trim() || rollingBackPromptFlowKey) {
      return;
    }
    const confirmed = window.confirm(
      "Se restaurara esta version y se sobrescribira la configuracion actual. Continuar?"
    );
    if (!confirmed) {
      return;
    }
    setRollingBackPromptFlowKey(flowKey);
    setErrorMessage(null);
    try {
      const updated = await rollbackPromptConfigApi(flowKey, versionId);
      setPromptConfigs((current) =>
        current.map((item) => (item.flow_key === updated.flow_key ? updated : item))
      );
      setPromptConfigDrafts((current) => ({
        ...current,
        [flowKey]: {
          template_text: updated.template_text,
          target_sources_input: updated.target_sources.join("\n"),
          is_active: updated.is_active
        }
      }));
      await loadPromptVersions(flowKey, true);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo restaurar la version seleccionada";
      setErrorMessage(message);
    } finally {
      setRollingBackPromptFlowKey((current) => (current === flowKey ? null : current));
    }
  }

  async function submitChatMessage(rawMessage: string) {
    if (!selectedPersonId || !rawMessage.trim() || isSendingMessage) {
      return;
    }
    const personId = selectedPersonId;
    const messageToSend = rawMessage.trim();
    setIsSendingMessage(true);
    setStreamingAssistantText("");
    setErrorMessage(null);
    let streamedAnyDelta = false;
    try {
      const updatedConversation = await sendMessageStream(
        personId,
        messageToSend,
        (delta) => {
          streamedAnyDelta = true;
          setStreamingAssistantText((current) => `${current}${delta}`);
        }
      );
      setConversation(updatedConversation);
      setChatInput("");
    } catch (error) {
      if (!streamedAnyDelta) {
        try {
          const updatedConversation = await sendMessage(personId, messageToSend);
          setConversation(updatedConversation);
          setChatInput("");
          setErrorMessage("Streaming no disponible. Se uso envio sin streaming como respaldo.");
          return;
        } catch {
          // Keep original stream failure message below.
        }
      }
      const message = error instanceof Error ? error.message : "No se pudo enviar el mensaje";
      setErrorMessage(message);
    } finally {
      setStreamingAssistantText("");
      setIsSendingMessage(false);
    }
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitChatMessage(chatInput);
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPersonId || !searchQuery.trim()) {
      return;
    }
    setIsSearching(true);
    setErrorMessage(null);
    setSearchProviderStatus([]);
    try {
      const payload = await searchOpportunities(selectedPersonId, searchQuery.trim(), 6);
      setSearchResults(payload.items);
      setSearchWarnings(payload.warnings);
      setSearchProviderStatus(payload.provider_status ?? []);
      setSelectedSearchResultId(null);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo ejecutar la busqueda";
      setErrorMessage(message);
    } finally {
      setIsSearching(false);
    }
  }

  async function handleSaveSearchResult(result: SearchResult) {
    if (!selectedPersonId) {
      return;
    }
    setSavingResultId(result.search_result_id);
    setErrorMessage(null);
    try {
      await saveOpportunityFromSearch(selectedPersonId, result);
      const items = await listOpportunities(selectedPersonId);
      setSavedOpportunities(items);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo guardar la oportunidad";
      setErrorMessage(message);
    } finally {
      setSavingResultId(null);
    }
  }

  async function handleCopyArtifactContent(copyKey: string, content: string) {
    const payload = content.trim();
    if (!payload) {
      setErrorMessage("No hay contenido para copiar.");
      return;
    }
    try {
      await copyToClipboard(payload);
      setCopiedArtifactKey(copyKey);
      window.setTimeout(() => {
        setCopiedArtifactKey((current) => (current === copyKey ? null : current));
      }, 1600);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo copiar el artefacto";
      setErrorMessage(message);
    }
  }

  async function handleCopyOpportunityUrl(opportunityId: string, url: string | null | undefined) {
    const payload = toExternalUrl(url) ?? String(url ?? "").trim();
    if (!payload) {
      setErrorMessage("URL no disponible para copiar.");
      return;
    }
    try {
      await copyToClipboard(payload);
      setCopiedOpportunityUrlId(opportunityId);
      window.setTimeout(() => {
        setCopiedOpportunityUrlId((current) => (current === opportunityId ? null : current));
      }, 1600);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo copiar la URL";
      setErrorMessage(message);
    }
  }

  async function handleToggleCvPreview() {
    if (!activeCv) {
      return;
    }
    if (isCvPreviewExpanded) {
      setIsCvPreviewExpanded(false);
      return;
    }
    if (!activeCvFullText && !isLoadingCvFullText) {
      setIsLoadingCvFullText(true);
      try {
        const payload = await getActiveCVText(activeCv.person_id);
        setActiveCvFullText((payload.structured_markdown || payload.extracted_text || "").trim());
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "No se pudo cargar el texto completo del CV";
        setErrorMessage(message);
      } finally {
        setIsLoadingCvFullText(false);
      }
    }
    setIsCvPreviewExpanded(true);
  }

  async function handleUploadCv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPersonId || !selectedCvFile || isUploadingCv) {
      return;
    }
    setIsUploadingCv(true);
    setErrorMessage(null);
    try {
      const payload = await uploadCV(selectedPersonId, selectedCvFile);
      setActiveCv(payload);
      setSelectedCvFile(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo cargar el CV";
      setErrorMessage(message);
    } finally {
      setIsUploadingCv(false);
    }
  }

  async function handleImportByUrl(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const sourceUrl = manualUrl.trim();
    const rawText = manualUrlRawText.trim();
    if (!selectedPersonId || !sourceUrl || isImportingUrl) {
      return;
    }
    if (rawText.length < 8) {
      setErrorMessage("La descripcion/snapshot es obligatoria (minimo 8 caracteres).");
      return;
    }
    setIsImportingUrl(true);
    setErrorMessage(null);
    try {
      const payload = await importOpportunityByUrl(selectedPersonId, {
        source_url: sourceUrl,
        title: manualUrlTitle.trim(),
        company: manualUrlCompany.trim(),
        location: manualUrlLocation.trim(),
        raw_text: rawText
      });
      const items = await listOpportunities(selectedPersonId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(payload.item.opportunity_id);
      setManualUrl("");
      setManualUrlTitle("");
      setManualUrlCompany("");
      setManualUrlLocation("");
      setManualUrlRawText("");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo importar por URL";
      setErrorMessage(message);
    } finally {
      setIsImportingUrl(false);
    }
  }

  function handleToggleSearchRole(role: string) {
    setSearchQuery((current) =>
      hasRoleToken(current, role)
        ? removeRoleToken(current, role)
        : addRoleToken(current, role)
    );
  }

  function handleSelectAllSearchRoles() {
    setSearchQuery((current) => {
      let next = current;
      for (const role of searchRoleKeywords) {
        next = addRoleToken(next, role);
      }
      return next;
    });
  }

  function handleClearSearchRoles() {
    setSearchQuery((current) => {
      let next = current;
      for (const role of searchRoleKeywords) {
        next = removeRoleToken(next, role);
      }
      return next;
    });
  }

  function waitMs(milliseconds: number) {
    return new Promise<void>((resolve) => {
      window.setTimeout(resolve, milliseconds);
    });
  }

  async function refreshAiRunsFor(personId: string, opportunityId: string): Promise<AIRun[]> {
    setIsLoadingAiRuns(true);
    try {
      const items = await listOpportunityAiRuns(personId, opportunityId);
      setAiRuns(items);
      return items;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo cargar el historico IA";
      if (message.includes("Opportunity not found")) {
        setAiRuns([]);
        setFocusedRunId("");
        return [];
      }
      setErrorMessage(message);
      return [];
    } finally {
      setIsLoadingAiRuns(false);
    }
  }

  async function refreshRequestTracesFor(
    personId: string,
    selectedOpportunityForScope: string,
    runId: string
  ) {
    setIsLoadingRequestTraces(true);
    try {
      const items = await listRequestTraces(personId, {
        opportunityId: selectedOpportunityForScope,
        runId,
        limit: 60
      });
      setRequestTraces(items);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo cargar trazas de prompts/API";
      if (message.includes("Opportunity not found")) {
        setRequestTraces([]);
        return;
      }
      setErrorMessage(message);
    } finally {
      setIsLoadingRequestTraces(false);
    }
  }

  async function refreshArtifacts(opportunityId: string) {
    if (!selectedPersonId) {
      return;
    }
    setIsLoadingArtifacts(true);
    try {
      const items = await listOpportunityArtifacts(selectedPersonId, opportunityId);
      setArtifacts(items);
    } finally {
      setIsLoadingArtifacts(false);
    }
  }

  async function handleAnalyzeProfileMatch(opportunityId: string, forceOverride?: boolean) {
    if (!selectedPersonId) {
      return;
    }
    const personId = selectedPersonId;
    const forceRecompute = forceOverride ?? forceRecomputeAi;
    setSelectedOpportunityId(opportunityId);
    setResultsPanelTab("analysis");
    setSelectedResultBlockId("analysis_profile_match");
    setIsAnalyzingProfile(true);
    setErrorMessage(null);
    setAnalysisText("");
    setProfileAnalysisText("");
    setCulturalConfidence("");
    setCulturalWarnings([]);
    setCulturalSignals([]);
    try {
      const payload = await analyzeProfileMatchStream(
        personId,
        opportunityId,
        forceRecompute,
        (delta) => {
          setAnalysisText((current) => `${current}${delta}`);
          setProfileAnalysisText((current) => `${current}${delta}`);
        }
      );
      setAnalysisText(payload.analysis_text);
      setProfileAnalysisText(payload.analysis_text);
      setSemanticEvidence(payload.semantic_evidence);
      setAnalyzeExecutedByOpportunity((current) => ({
        ...current,
        [opportunityId]: true
      }));
      const items = await listOpportunities(personId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
      await refreshAiRunsFor(personId, opportunityId);
    } catch (error) {
      try {
        const payload = await analyzeProfileMatch(personId, opportunityId, forceRecompute);
        setAnalysisText(payload.analysis_text);
        setProfileAnalysisText(payload.analysis_text);
        setSemanticEvidence(payload.semantic_evidence);
        setAnalyzeExecutedByOpportunity((current) => ({
          ...current,
          [opportunityId]: true
        }));
        const items = await listOpportunities(personId);
        setSavedOpportunities(items);
        setSelectedOpportunityId(opportunityId);
        await refreshAiRunsFor(personId, opportunityId);
        setErrorMessage(
          "Streaming de analisis no disponible. Se uso endpoint sin streaming como respaldo."
        );
      } catch {
        const message =
          error instanceof Error ? error.message : "No se pudo analizar perfil-vacante";
        setErrorMessage(message);
      }
    } finally {
      setIsAnalyzingProfile(false);
    }
  }

  async function handleAnalyzeCulturalFit(opportunityId: string, forceOverride?: boolean) {
    if (!selectedPersonId) {
      return;
    }
    const personId = selectedPersonId;
    const forceRecompute = forceOverride ?? forceRecomputeAi;
    setSelectedOpportunityId(opportunityId);
    setResultsPanelTab("analysis");
    setSelectedResultBlockId("analysis_cultural_fit");
    setIsAnalyzingCultural(true);
    setErrorMessage(null);
    setCulturalConfidence("");
    setCulturalWarnings([]);
    setCulturalSignals([]);
    setAnalysisText("");
    setCultureAnalysisText("");
    setSemanticEvidence(null);
    try {
      const payload = await analyzeCulturalFitStream(
        personId,
        opportunityId,
        forceRecompute,
        (delta) => {
          setAnalysisText((current) => `${current}${delta}`);
          setCultureAnalysisText((current) => `${current}${delta}`);
        }
      );
      setAnalysisText(payload.analysis_text);
      setCultureAnalysisText(payload.analysis_text);
      setCulturalConfidence(payload.cultural_confidence);
      setCulturalWarnings(payload.cultural_warnings);
      setCulturalSignals(payload.cultural_signals);
      setAnalyzeExecutedByOpportunity((current) => ({
        ...current,
        [opportunityId]: true
      }));
      const items = await listOpportunities(personId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
      await refreshAiRunsFor(personId, opportunityId);
    } catch (error) {
      try {
        const payload = await analyzeCulturalFit(personId, opportunityId, forceRecompute);
        setAnalysisText(payload.analysis_text);
        setCultureAnalysisText(payload.analysis_text);
        setCulturalConfidence(payload.cultural_confidence);
        setCulturalWarnings(payload.cultural_warnings);
        setCulturalSignals(payload.cultural_signals);
        setAnalyzeExecutedByOpportunity((current) => ({
          ...current,
          [opportunityId]: true
        }));
        const items = await listOpportunities(personId);
        setSavedOpportunities(items);
        setSelectedOpportunityId(opportunityId);
        await refreshAiRunsFor(personId, opportunityId);
        setErrorMessage(
          "Streaming de analisis no disponible. Se uso endpoint sin streaming como respaldo."
        );
      } catch {
        const message = error instanceof Error ? error.message : "No se pudo analizar fit cultural";
        setErrorMessage(message);
      }
    } finally {
      setIsAnalyzingCultural(false);
    }
  }

  async function handleInterviewBrief(opportunityId: string, forceOverride?: boolean) {
    if (!selectedPersonId) {
      return;
    }
    const personId = selectedPersonId;
    const forceRecompute = forceOverride ?? forceRecomputeAi;
    const previousInterviewCount = aiRuns.filter(
      (item) => item.action_key === "interview_brief"
    ).length;
    setSelectedOpportunityId(opportunityId);
    setResultsPanelTab("analysis");
    setSelectedResultBlockId("analysis_interview_brief");
    setIsChatDrawerOpen(true);
    setIsInterviewing(true);
    setErrorMessage(null);
    setAnalysisText("");
    setInterviewBriefText("");
    let receivedInterviewDelta = false;
    try {
      const payload = await interviewBriefStream(
        personId,
        opportunityId,
        forceRecompute,
        (delta) => {
          receivedInterviewDelta = true;
          setAnalysisText((current) => `${current}${delta}`);
          setInterviewBriefText((current) => `${current}${delta}`);
        }
      );
      setAnalysisText(payload.analysis_text);
      setInterviewBriefText(payload.analysis_text);
      setSemanticEvidence(payload.semantic_evidence);
      setAnalyzeExecutedByOpportunity((current) => ({
        ...current,
        [opportunityId]: true
      }));
      const [items, conversationPayload] = await Promise.all([
        listOpportunities(personId),
        getConversation(personId)
      ]);
      setConversation(conversationPayload);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
      let latestRuns = await refreshAiRunsFor(personId, opportunityId);
      if (forceRecompute) {
        const expectedMinRuns = previousInterviewCount + 1;
        let attempts = 0;
        while (
          latestRuns.filter((item) => item.action_key === "interview_brief").length < expectedMinRuns
          && attempts < 4
        ) {
          attempts += 1;
          await waitMs(300);
          latestRuns = await refreshAiRunsFor(personId, opportunityId);
        }
      }
      setRunCursorByAction((current) => ({
        ...current,
        interview_brief: 0
      }));
    } catch (error) {
      try {
        // Si no llego ningun delta y se solicito refresco, fallback mantiene recálculo.
        // Si ya hubo deltas (o no era refresh), fallback prioriza cache para evitar duplicados.
        const fallbackForceRecompute = forceRecompute && !receivedInterviewDelta;
        const payload = await interviewBrief(personId, opportunityId, fallbackForceRecompute);
        setAnalysisText(payload.analysis_text);
        setInterviewBriefText(payload.analysis_text);
        setSemanticEvidence(payload.semantic_evidence);
        setAnalyzeExecutedByOpportunity((current) => ({
          ...current,
          [opportunityId]: true
        }));
        const [items, conversationPayload] = await Promise.all([
          listOpportunities(personId),
          getConversation(personId)
        ]);
        setConversation(conversationPayload);
        setSavedOpportunities(items);
        setSelectedOpportunityId(opportunityId);
        let latestRuns = await refreshAiRunsFor(personId, opportunityId);
        if (forceRecompute) {
          const expectedMinRuns = previousInterviewCount + 1;
          let attempts = 0;
          while (
            latestRuns.filter((item) => item.action_key === "interview_brief").length
              < expectedMinRuns
            && attempts < 4
          ) {
            attempts += 1;
            await waitMs(300);
            latestRuns = await refreshAiRunsFor(personId, opportunityId);
          }
        }
        setRunCursorByAction((current) => ({
          ...current,
          interview_brief: 0
        }));
        setErrorMessage(
          "Streaming de entrevista no disponible. Se uso endpoint sin streaming como respaldo."
        );
      } catch {
        const message = error instanceof Error ? error.message : "No se pudo generar brief de entrevista";
        setErrorMessage(message);
      }
    } finally {
      setIsInterviewing(false);
    }
  }

  async function handlePrepare(
    opportunityId: string,
    forceOverride?: boolean,
    explicitTargets?: Array<"guidance_text" | "cover_letter" | "experience_summary">
  ) {
    if (!selectedPersonId) {
      return;
    }
    const personId = selectedPersonId;
    const forceRecompute = forceOverride ?? forceRecomputeAi;
    const targets: Array<"guidance_text" | "cover_letter" | "experience_summary"> =
      explicitTargets && explicitTargets.length > 0
        ? [...explicitTargets]
        : ["guidance_text", "cover_letter", "experience_summary"];
    if (targets.length === 0) {
      setErrorMessage("Selecciona al menos un material para preparar.");
      return;
    }

    setSelectedOpportunityId(opportunityId);
    setResultsPanelTab("artifacts");
    if (targets.length === 1) {
      const target = targets[0];
      setSelectedResultBlockId(
        target === "guidance_text"
          ? "artifact_guidance_text"
          : target === "cover_letter"
            ? "artifact_cover_letter"
            : "artifact_experience_summary"
      );
    }
    setIsPreparing(true);
    setErrorMessage(null);
    if (targets.includes("guidance_text")) {
      setGuidanceText("");
    }
    setArtifacts((current) =>
      current.filter((item) => {
        if (item.artifact_type === "cover_letter" && targets.includes("cover_letter")) {
          return false;
        }
        if (
          item.artifact_type === "experience_summary" &&
          targets.includes("experience_summary")
        ) {
          return false;
        }
        return true;
      })
    );

    try {
      const payload = await prepareOpportunityStream(
        personId,
        opportunityId,
        {
          targets,
          force_recompute: forceRecompute
        },
        (channel, delta) => {
          if (channel === "guidance_text") {
            setGuidanceText((current) => `${current}${delta}`);
            return;
          }
          if (channel === "cover_letter") {
            setArtifacts((current) =>
              appendArtifactDelta(
                current,
                personId,
                opportunityId,
                "cover_letter",
                delta
              )
            );
            return;
          }
          if (channel === "experience_summary") {
            setArtifacts((current) =>
              appendArtifactDelta(
                current,
                personId,
                opportunityId,
                "experience_summary",
                delta
              )
            );
          }
        }
      );
      setGuidanceText(payload.guidance_text);
      setArtifacts(payload.artifacts);
      setSemanticEvidence(payload.semantic_evidence);
      setArtifactsExecutedByOpportunity((current) => ({
        ...current,
        [opportunityId]: true
      }));
      const items = await listOpportunities(personId);
      setSavedOpportunities(items);
      setSelectedOpportunityId(opportunityId);
      await refreshAiRunsFor(personId, opportunityId);
    } catch (error) {
      try {
        const payload = await prepareOpportunity(
          personId,
          opportunityId,
          {
            targets,
            force_recompute: forceRecompute
          }
        );
        setGuidanceText(payload.guidance_text);
        setArtifacts(payload.artifacts);
        setSemanticEvidence(payload.semantic_evidence);
        setArtifactsExecutedByOpportunity((current) => ({
          ...current,
          [opportunityId]: true
        }));
        const items = await listOpportunities(personId);
        setSavedOpportunities(items);
        setSelectedOpportunityId(opportunityId);
        await refreshAiRunsFor(personId, opportunityId);
        setErrorMessage(
          "Streaming de preparacion no disponible. Se uso endpoint sin streaming como respaldo."
        );
      } catch {
        const message =
          error instanceof Error ? error.message : "No se pudo preparar postulacion";
        setErrorMessage(message);
      }
    } finally {
      setIsPreparing(false);
    }
  }

  function handleSelectOpportunityCard(opportunityId: string) {
    setSelectedOpportunityId((current) => (current === opportunityId ? null : opportunityId));
  }

  async function handleSaveNotes() {
    if (!selectedPersonId || !selectedOpportunityId || isSavingNotes) {
      return;
    }
    setIsSavingNotes(true);
    setErrorMessage(null);
    try {
      const updated = await updateOpportunity(selectedPersonId, selectedOpportunityId, {
        notes: opportunityNotes
      });
      setSavedOpportunities((current) =>
        current.map((item) =>
          item.opportunity_id === updated.opportunity_id ? updated : item
        )
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudieron guardar las notas";
      setErrorMessage(message);
    } finally {
      setIsSavingNotes(false);
    }
  }

  async function handleSaveStatus() {
    if (!selectedPersonId || !selectedOpportunityId || isSavingStatus) {
      return;
    }
    setIsSavingStatus(true);
    setStatusSaveMessage(null);
    setErrorMessage(null);
    try {
      const updated = await updateOpportunity(selectedPersonId, selectedOpportunityId, {
        status: opportunityStatus
      });
      setSavedOpportunities((current) =>
        current.map((item) =>
          item.opportunity_id === updated.opportunity_id ? updated : item
        )
      );
      setStatusSaveMessage("Estado actualizado");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo guardar el estado";
      setErrorMessage(message);
    } finally {
      setIsSavingStatus(false);
    }
  }

  async function handleSaveCulturePreferences() {
    if (!selectedPersonId || isSavingCulturePreferences) {
      return;
    }
    setIsSavingCulturePreferences(true);
    setErrorMessage(null);
    try {
      const updated = await updatePersonProfile(selectedPersonId, {
        cultural_fit_preferences: culturePreferencesState,
        culture_preferences_notes: culturePreferencesNotes
      });
      setPeople((current) =>
        current.map((item) => (item.person_id === updated.person_id ? updated : item))
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudieron guardar las preferencias";
      setErrorMessage(message);
    } finally {
      setIsSavingCulturePreferences(false);
    }
  }

  async function handleSaveProfile() {
    if (!selectedPersonId || isSavingProfile) {
      return;
    }
    const fullName = profileFullName.trim();
    const location = profileLocation.trim();
    const yearsExperience = Number.parseInt(profileYearsExperienceInput.trim(), 10);
    const salaryMinInput = profileSalaryMinInput.trim();
    const salaryMaxInput = profileSalaryMaxInput.trim();
    const salaryMin = salaryMinInput ? Number.parseInt(salaryMinInput, 10) : null;
    const salaryMax = salaryMaxInput ? Number.parseInt(salaryMaxInput, 10) : null;
    const salaryCurrency = profileSalaryCurrency.trim();
    const salaryPeriod = profileSalaryPeriod.trim();
    const targetRoles = profileTargetRolesInput
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);
    const skills = profileSkillsInput
      .split(/[\n,]/g)
      .map((item) => item.trim())
      .filter(Boolean);

    if (!fullName || !location || targetRoles.length === 0 || skills.length === 0) {
      setErrorMessage("Perfil incompleto: nombre, ubicacion, roles y skills son obligatorios.");
      return;
    }
    if (!Number.isFinite(yearsExperience) || yearsExperience < 0 || yearsExperience > 80) {
      setErrorMessage("Años de experiencia debe estar entre 0 y 80.");
      return;
    }
    if (
      (salaryMinInput && !Number.isFinite(salaryMin)) ||
      (salaryMaxInput && !Number.isFinite(salaryMax))
    ) {
      setErrorMessage("Expectativa salarial debe ser numerica.");
      return;
    }
    if (salaryMin !== null && salaryMax !== null && salaryMin > salaryMax) {
      setErrorMessage("Expectativa salarial invalida: el minimo supera el maximo.");
      return;
    }
    if (salaryCurrency && !SALARY_CURRENCIES.includes(salaryCurrency as (typeof SALARY_CURRENCIES)[number])) {
      setErrorMessage("Moneda salarial invalida.");
      return;
    }
    if (
      salaryPeriod
      && !SALARY_PERIODS.some((item) => item.value === salaryPeriod)
    ) {
      setErrorMessage("Periodo salarial invalido.");
      return;
    }

    setIsSavingProfile(true);
    setErrorMessage(null);
    try {
      const updated = await updatePersonProfile(selectedPersonId, {
        full_name: fullName,
        target_roles: targetRoles,
        location,
        years_experience: yearsExperience,
        skills,
        salary_expectation_min: salaryMin,
        salary_expectation_max: salaryMax,
        salary_currency: salaryCurrency,
        salary_period: salaryPeriod
      });
      setPeople((current) =>
        current.map((item) => (item.person_id === updated.person_id ? updated : item))
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "No se pudo guardar el perfil";
      setErrorMessage(message);
    } finally {
      setIsSavingProfile(false);
    }
  }

  function handleToggleCulturalOption(fieldId: string, optionValue: string, checked: boolean) {
    setCulturePreferencesState((current) => {
      const existing = current[fieldId] ?? {
        enabled: false,
        selected_values: [],
        criticality: "normal"
      };
      const selected = checked
        ? Array.from(new Set([...existing.selected_values, optionValue]))
        : existing.selected_values.filter((value) => value !== optionValue);
      return {
        ...current,
        [fieldId]: {
          ...existing,
          enabled: selected.length > 0,
          selected_values: selected
        }
      };
    });
  }

  function handleSwitchResultsTab(nextTab: "analysis" | "artifacts") {
    const blockOrder = nextTab === "analysis" ? ANALYSIS_BLOCK_ORDER : ARTIFACT_BLOCK_ORDER;
    const firstWithRun = blockOrder.find((blockId) => getRunsForBlock(blockId).length > 0);
    setResultsPanelTab(nextTab);
    setSelectedResultBlockId(firstWithRun ?? blockOrder[0]);
  }

  function handleSelectResultBlock(blockId: AnalysisResultBlockId) {
    setSelectedResultBlockId(blockId);
  }

  function handleToggleResultBlockPreview(blockId: AnalysisResultBlockId) {
    setExpandedResultBlocks((current) => ({
      ...current,
      [blockId]: !current[blockId]
    }));
  }

  function getCurrentRunIndexForBlock(blockId: AnalysisResultBlockId) {
    const actionKey = BLOCK_RUN_ACTION_BY_ID[blockId];
    const runs = getRunsForBlock(blockId);
    if (runs.length === 0) {
      return 0;
    }
    const cursor = runCursorByAction[actionKey] ?? 0;
    return Math.min(Math.max(cursor, 0), runs.length - 1);
  }

  function handleMoveRunCursor(blockId: AnalysisResultBlockId, delta: number) {
    const actionKey = BLOCK_RUN_ACTION_BY_ID[blockId];
    const runs = getRunsForBlock(blockId);
    if (runs.length === 0) {
      return;
    }
    setRunCursorByAction((current) => {
      const cursor = current[actionKey] ?? 0;
      const nextCursor = Math.min(Math.max(cursor + delta, 0), runs.length - 1);
      return {
        ...current,
        [actionKey]: nextCursor
      };
    });
    setSelectedResultBlockId(blockId);
  }

  function getArtifactFallbackContent(artifactType: "cover_letter" | "experience_summary") {
    const artifact = artifacts.find((item) => item.artifact_type === artifactType);
    return artifact?.content?.trim() ?? "";
  }

  const profileRun = getSelectedRunForBlock("analysis_profile_match");
  const culturalRun = getSelectedRunForBlock("analysis_cultural_fit");
  const interviewRun = getSelectedRunForBlock("analysis_interview_brief");
  const guidanceRun = getSelectedRunForBlock("artifact_guidance_text");
  const coverRun = getSelectedRunForBlock("artifact_cover_letter");
  const summaryRun = getSelectedRunForBlock("artifact_experience_summary");
  const profileRuns = getRunsForBlock("analysis_profile_match");
  const culturalRuns = getRunsForBlock("analysis_cultural_fit");
  const interviewRuns = getRunsForBlock("analysis_interview_brief");
  const guidanceRuns = getRunsForBlock("artifact_guidance_text");
  const coverRuns = getRunsForBlock("artifact_cover_letter");
  const summaryRuns = getRunsForBlock("artifact_experience_summary");
  const getRunPreview = (run: AIRun | null) => (run ? getAiRunPreviewText(run) : "");

  const liveProfileContent = isAnalyzingProfile ? profileAnalysisText : "";
  const liveCulturalContent = isAnalyzingCultural ? cultureAnalysisText : "";
  const liveInterviewContent = isInterviewing ? interviewBriefText : "";
  const liveGuidanceContent = isPreparing ? guidanceText : "";
  const liveCoverContent = getArtifactFallbackContent("cover_letter");
  const liveSummaryContent = getArtifactFallbackContent("experience_summary");

  const profileContent = liveProfileContent || getRunPreview(profileRun);
  const culturalContent = liveCulturalContent || getRunPreview(culturalRun);
  const interviewContent = liveInterviewContent || getRunPreview(interviewRun);
  const guidanceContent = liveGuidanceContent || getRunPreview(guidanceRun) || guidanceText;
  const coverContent = (isPreparing ? liveCoverContent : "") || getRunPreview(coverRun) || liveCoverContent;
  const summaryContent =
    (isPreparing ? liveSummaryContent : "") || getRunPreview(summaryRun) || liveSummaryContent;

  const profilePreview = buildContentLinePreview(
    profileContent,
    7,
    expandedResultBlocks.analysis_profile_match
  );
  const culturalPreview = buildContentLinePreview(
    culturalContent,
    7,
    expandedResultBlocks.analysis_cultural_fit
  );
  const guidancePreview = buildContentLinePreview(
    guidanceContent,
    7,
    expandedResultBlocks.artifact_guidance_text
  );
  const interviewPreview = buildContentLinePreview(
    interviewContent,
    7,
    expandedResultBlocks.analysis_interview_brief
  );
  const coverPreview = buildContentLinePreview(
    coverContent,
    7,
    expandedResultBlocks.artifact_cover_letter
  );
  const summaryPreview = buildContentLinePreview(
    summaryContent,
    7,
    expandedResultBlocks.artifact_experience_summary
  );
  const culturalConfidenceView = culturalRun
    ? String(culturalRun.result_payload["cultural_confidence"] ?? "").trim()
    : culturalConfidence;
  const culturalWarningsView = culturalRun
    ? asStringArray(culturalRun.result_payload["cultural_warnings"])
    : culturalWarnings;
  const culturalSignalsView = culturalRun
    ? asCulturalSignals(culturalRun.result_payload["cultural_signals"])
    : culturalSignals;
  const interviewSignalsView = interviewRun
    ? asCulturalSignals(interviewRun.result_payload["interview_sources"])
    : [];
  const interviewIterationsView = interviewRun
    ? asInterviewIterations(interviewRun.result_payload["interview_iterations"])
    : [];
  const profilePromptBadge = getPromptBadgeForFlow(
    profileRun?.result_payload,
    "task_analyze_profile_match"
  );
  const culturalPromptBadge = getPromptBadgeForFlow(
    culturalRun?.result_payload,
    "task_analyze_cultural_fit"
  );
  const interviewPromptBadge = getPromptBadgeForFlow(
    interviewRun?.result_payload,
    "task_interview_brief"
  );
  const guidancePromptBadge = getPromptBadgeForFlow(
    guidanceRun?.result_payload,
    "task_prepare_guidance"
  );
  const coverPromptBadge = getPromptBadgeForFlow(
    coverRun?.result_payload,
    "task_prepare_cover_letter"
  );
  const summaryPromptBadge = getPromptBadgeForFlow(
    summaryRun?.result_payload,
    "task_prepare_experience_summary"
  );
  const interviewReferenceUrls = Array.from(
    new Set(
      [
        ...interviewSignalsView.map((item) => item.source_url),
        ...interviewIterationsView.flatMap((item) => item.top_urls),
      ]
        .map((value) => String(value ?? "").trim())
        .filter((value) => value.length > 0)
    )
  );

  if (view === "checking") {
    return (
      <main className="shell">
        <section className="panel">
          <p className="eyebrow">Tutor Workspace</p>
          <h1 className="compactTitle">Validando sesion...</h1>
        </section>
      </main>
    );
  }

  if (view === "login") {
    return (
      <main className="shell">
        <section className="hero">
          <p className="eyebrow">Tutor Workspace</p>
          <h1>Acceso protegido del tutor.</h1>
          <p className="lede">
            Inicia sesion para seleccionar un perfil y abrir su
            contexto de trabajo.
          </p>
        </section>

        <section className="panel authPanel">
          <form className="authForm" onSubmit={handleLogin}>
            <label className="field">
              Usuario
              <input
                autoComplete="username"
                name="username"
                onChange={(event) => setUsername(event.target.value)}
                value={username}
              />
            </label>
            <label className="field">
              Contrasena
              <input
                autoComplete="current-password"
                name="password"
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                value={password}
              />
            </label>
            {errorMessage ? <p className="errorText">{errorMessage}</p> : null}
            <button className="primaryButton" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Ingresando..." : "Ingresar"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className={shellClassName}>
      <section className="panel workspaceTopbar">
        <div className="workspaceBrand">
          <p className="eyebrow workspaceBrandWordmark">
            <span>Career</span>
            <span className="workspaceBrandIq">IQ</span>
          </p>
        </div>
        <div className="workspaceCenter">
          {selectedPerson ? (
            <div className="contextSelector">
              <button
                className="contextSelectorButton"
                onClick={() =>
                  setIsPersonContextMenuOpen((current) => !current)
                }
                type="button"
              >
                <span className="candidateAvatar contextSelectorAvatar">
                  {getPersonInitials(selectedPerson.full_name)}
                </span>
                <span className="contextSelectorText">
                  <strong>{selectedPerson.full_name}</strong>
                  <span>{selectedPerson.target_roles[0] ?? "Sin rol objetivo"}</span>
                </span>
                <span className="contextSelectorChevron">
                  {isPersonContextMenuOpen ? "▴" : "▾"}
                </span>
              </button>
              {isPersonContextMenuOpen ? (
                <article className="contextSelectorMenu">
                  <p className="metaText">
                    Operador: <strong>{operatorName}</strong>
                  </p>
                  <div className="contextSelectorMenuActions">
                    <button
                      onClick={() => {
                        setIsPersonContextMenuOpen(false);
                        navigateTo("/candidates");
                      }}
                      type="button"
                    >
                      Cambiar candidato
                    </button>
                    <button
                      onClick={() => {
                        setIsPersonContextMenuOpen(false);
                        navigateTo(buildContextPath(selectedPerson.person_id, "profile"));
                      }}
                      type="button"
                    >
                      Ver perfil activo
                    </button>
                  </div>
                </article>
              ) : null}
            </div>
          ) : (
            <button
              className="contextSelectorButton contextSelectorButtonEmpty"
              onClick={() => navigateTo("/candidates")}
              type="button"
            >
              Seleccionar candidato
            </button>
          )}
        </div>
        <div className="workspaceRight">
          {selectedPerson ? (
            <nav className="workspaceTabs" aria-label="Navegacion contextual">
              <button
                className={showProfilePage ? "workspaceTabButton workspaceTabButtonActive" : "workspaceTabButton"}
                onClick={() => navigateTo(buildContextPath(selectedPerson.person_id, "profile"))}
                type="button"
              >
                Perfil
              </button>
              <button
                className={
                  showOpportunitiesPage
                    ? "workspaceTabButton workspaceTabButtonActive"
                    : "workspaceTabButton"
                }
                onClick={() =>
                  navigateTo(buildContextPath(selectedPerson.person_id, "opportunities"))
                }
                type="button"
              >
                Vacantes
              </button>
              <button
                className={
                  showAnalysisPage
                    ? "workspaceTabButton workspaceTabButtonActive"
                    : "workspaceTabButton"
                }
                onClick={() => navigateTo(buildContextPath(selectedPerson.person_id, "analysis"))}
                type="button"
              >
                Análisis
              </button>
            </nav>
          ) : null}
          <div className="iconActionGroup">
            <button
              className={
                showAdminPromptsPage
                  ? "iconActionButton iconActionButtonActive"
                  : "iconActionButton"
              }
              onClick={() => navigateTo("/admin/prompts")}
              title="Administracion"
              type="button"
            >
              <svg
                aria-hidden="true"
                className="iconActionSvg"
                fill="none"
                height="16"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
                width="16"
              >
                <circle cx="12" cy="12" r="3.25" />
                <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2h.1a1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1v.1a1 1 0 0 0 .9.6H20a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.9.6z" />
              </svg>
              <span className="srOnly">Administracion</span>
            </button>
            <button
              className="iconActionButton"
              onClick={handleLogout}
              title="Cerrar sesion"
              type="button"
            >
              <svg
                aria-hidden="true"
                className="iconActionSvg"
                fill="none"
                height="16"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.8"
                viewBox="0 0 24 24"
                width="16"
              >
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <path d="m16 17 5-5-5-5" />
                <path d="M21 12H9" />
              </svg>
              <span className="srOnly">Cerrar sesion</span>
            </button>
          </div>
        </div>
      </section>

      <section className={showProfilePage || showCandidatesPage ? "hero heroCompact" : "hero"}>
        <p className="eyebrow">{currentPageLabel}</p>
        <h1 className={showProfilePage || showCandidatesPage ? "heroTitleCompact" : undefined}>
          {currentPageTitle}
        </h1>
        {currentPageLede ? <p className="lede">{currentPageLede}</p> : null}
      </section>

      {showCandidatesPage ? (
        <section className="panel">
        <header className="panelHeader">
          <div>
            <h2>Perfiles consultados</h2>
            <p>Selecciona el perfil activo para continuar a busqueda y alineacion.</p>
          </div>
          <div className="cardActions">
            <p className="metaText">{people.length} registrados</p>
            <button
              className={isCreateProfileFormOpen ? "activeButton" : ""}
              onClick={() =>
                setIsCreateProfileFormOpen((current) => !current)
              }
              type="button"
            >
              {isCreateProfileFormOpen ? "Ocultar alta" : "Agregar perfil"}
            </button>
          </div>
        </header>

        <div className="cards candidateCards">
          {people.map((person) => (
            <article
              className={
                person.person_id === selectedPersonId
                  ? "card candidateSelectionCard candidateSelectionCardActive"
                  : "card candidateSelectionCard"
              }
              key={person.person_id}
              onClick={() => {
                setSelectedPersonId(person.person_id);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedPersonId(person.person_id);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <div className="cardHeader">
                <div className="candidateAvatar">{getPersonInitials(person.full_name)}</div>
                <div>
                  <span className="cardTag">{person.person_id}</span>
                  <h3>{person.full_name}</h3>
                </div>
              </div>
              <p>{person.target_roles[0] ?? "Sin rol objetivo"}</p>
              <p className="metaText">
                {person.location} · {person.years_experience} años
              </p>
            </article>
          ))}
        </div>
        {isCreateProfileFormOpen ? (
          <>
            <h3 className="subheading">Agregar perfil</h3>
            <form className="manualCard" onSubmit={handleCreatePerson}>
              <label className="field">
                Nombre completo
                <input
                  disabled={isCreatingPerson}
                  onChange={(event) => setNewPersonFullName(event.target.value)}
                  value={newPersonFullName}
                />
              </label>
              <div className="manualRow">
                <label className="field">
                  Ubicacion
                  <input
                    disabled={isCreatingPerson}
                    onChange={(event) => setNewPersonLocation(event.target.value)}
                    value={newPersonLocation}
                  />
                </label>
                <label className="field">
                  Años de experiencia
                  <input
                    disabled={isCreatingPerson}
                    max={80}
                    min={0}
                    onChange={(event) => setNewPersonYearsExperienceInput(event.target.value)}
                    type="number"
                    value={newPersonYearsExperienceInput}
                  />
                </label>
              </div>
              <label className="field">
                Roles objetivo (coma o salto de linea)
                <textarea
                  disabled={isCreatingPerson}
                  onChange={(event) => setNewPersonTargetRolesInput(event.target.value)}
                  rows={2}
                  value={newPersonTargetRolesInput}
                />
              </label>
              <label className="field">
                Skills (coma o salto de linea)
                <textarea
                  disabled={isCreatingPerson}
                  onChange={(event) => setNewPersonSkillsInput(event.target.value)}
                  rows={2}
                  value={newPersonSkillsInput}
                />
              </label>
              <div className="cardActions">
                <button className="primaryButton" disabled={isCreatingPerson} type="submit">
                  {isCreatingPerson ? "Creando..." : "Crear perfil"}
                </button>
              </div>
            </form>
          </>
        ) : null}
        </section>
      ) : null}

      {showAdminPromptsPage ? (
        <section className="panel selectedPanel">
        <header className="panelHeader">
          <div>
            <h2>Administracion de proveedores de busqueda</h2>
            <p>
              Habilita o deshabilita proveedores de vacantes desde UI para controlar
              conectividad y diagnostico.
            </p>
          </div>
          <button
            className="ghostButton"
            disabled={
              isLoadingSearchProviderConfigs || isLoadingPromptConfigs || isLoadingAiRuntimeConfig
            }
            onClick={() => setPromptConfigReloadToken((current) => current + 1)}
            type="button"
          >
            {isLoadingSearchProviderConfigs ? "Actualizando..." : "Refrescar"}
          </button>
        </header>
        {isLoadingSearchProviderConfigs ? (
          <p className="metaText">Cargando proveedores...</p>
        ) : orderedSearchProviderConfigs.length === 0 ? (
          <p className="metaText">No hay proveedores configurados.</p>
        ) : (
          <div className="promptConfigGrid">
            {orderedSearchProviderConfigs.map((provider) => {
              const isSaving = savingSearchProviderKey === provider.provider_key;
              return (
                <article className="manualCard" key={provider.provider_key}>
                  <p className="chatRole">
                    {SEARCH_PROVIDER_LABELS[provider.provider_key] ?? provider.provider_key}
                  </p>
                  <p className="metaText">provider_key: {provider.provider_key}</p>
                  <label className="checkboxRow">
                    <input
                      checked={provider.is_enabled}
                      disabled={isSaving}
                      onChange={(event) =>
                        void handleToggleSearchProvider(
                          provider.provider_key,
                          event.target.checked
                        )
                      }
                      type="checkbox"
                    />
                    <span>Proveedor habilitado</span>
                  </label>
                  <p className="metaText">
                    Ultima actualizacion: {new Date(provider.updated_at).toLocaleString()} por{" "}
                    {provider.updated_by}
                  </p>
                </article>
              );
            })}
          </div>
        )}
        </section>
      ) : null}

      {showAdminPromptsPage ? (
        <section className="panel selectedPanel">
          <header className="panelHeader">
            <div>
              <h2>Administracion de retrieval semantico (global V1)</h2>
              <p>
                Controla top_k por contexto: analisis/preparacion en produccion y entrevista
                (preconfigurado para proxima fase).
              </p>
            </div>
          </header>
          {isLoadingAiRuntimeConfig ? (
            <p className="metaText">Cargando configuracion de IA...</p>
          ) : !aiRuntimeConfig ? (
            <p className="metaText">No hay configuracion de IA disponible.</p>
          ) : (
            <div className="promptConfigGrid">
              <article className="manualCard">
                <p className="chatRole">Control de retrieval y modo agéntico</p>
                <p className="metaText">
                  Rango permitido: {AI_RUNTIME_TOP_K_MIN} a {AI_RUNTIME_TOP_K_MAX}
                </p>
                <label className="field">
                  top_k semantico para analisis/preparacion
                  <input
                    disabled={isSavingAiRuntimeConfig}
                    max={AI_RUNTIME_TOP_K_MAX}
                    min={AI_RUNTIME_TOP_K_MIN}
                    onChange={(event) => setAiRuntimeTopKAnalysisInput(event.target.value)}
                    step={1}
                    type="number"
                    value={aiRuntimeTopKAnalysisInput}
                  />
                </label>
                <label className="field">
                  top_k semantico para entrevista
                  <input
                    disabled={isSavingAiRuntimeConfig}
                    max={AI_RUNTIME_TOP_K_MAX}
                    min={AI_RUNTIME_TOP_K_MIN}
                    onChange={(event) => setAiRuntimeTopKInterviewInput(event.target.value)}
                    step={1}
                    type="number"
                    value={aiRuntimeTopKInterviewInput}
                  />
                </label>
                <label className="field">
                  Estrategia de chunking para CV
                  <select
                    disabled={isSavingAiRuntimeConfig}
                    onChange={(event) =>
                      setAiRuntimeCvChunkingStrategyInput(
                        event.target.value as "token_window" | "semantic_sections"
                      )
                    }
                    value={aiRuntimeCvChunkingStrategyInput}
                  >
                    <option value="semantic_sections">semantic_sections (por bloques semanticos)</option>
                    <option value="token_window">token_window (ventana fija de tokens)</option>
                  </select>
                </label>
                <p className="metaText">
                  Se aplica en nuevas indexaciones de CV. Para CV ya cargados, requiere recarga/reindex.
                </p>
                <label className="field">
                  Estrategia de extraccion Markdown de CV
                  <select
                    disabled={isSavingAiRuntimeConfig}
                    onChange={(event) =>
                      setAiRuntimeCvMarkdownExtractionModeInput(
                        event.target.value as "heuristic" | "pymupdf4llm"
                      )
                    }
                    value={aiRuntimeCvMarkdownExtractionModeInput}
                  >
                    <option value="heuristic">heuristic (actual, estable)</option>
                    <option value="pymupdf4llm">pymupdf4llm (mejor jerarquia PDF)</option>
                  </select>
                </label>
                <p className="metaText">
                  Solo afecta nuevas cargas de CV. Si falta dependencia, cae a heuristic con fallback seguro.
                </p>
                <label className="field">
                  Modo de investigacion de entrevista
                  <select
                    disabled={isSavingAiRuntimeConfig}
                    onChange={(event) =>
                      setAiRuntimeInterviewResearchModeInput(
                        event.target.value as "guided" | "adaptive"
                      )
                    }
                    value={aiRuntimeInterviewResearchModeInput}
                  >
                    <option value="guided">guided (pasos fijos)</option>
                    <option value="adaptive">adaptive (plan dinamico)</option>
                  </select>
                </label>
                <label className="field">
                  max steps de investigacion entrevista
                  <input
                    disabled={isSavingAiRuntimeConfig}
                    max={AI_RUNTIME_INTERVIEW_STEPS_MAX}
                    min={AI_RUNTIME_INTERVIEW_STEPS_MIN}
                    onChange={(event) => setAiRuntimeInterviewMaxStepsInput(event.target.value)}
                    step={1}
                    type="number"
                    value={aiRuntimeInterviewMaxStepsInput}
                  />
                </label>
                <p className="metaText">
                  steps permitidos: {AI_RUNTIME_INTERVIEW_STEPS_MIN} a {AI_RUNTIME_INTERVIEW_STEPS_MAX}
                </p>
                <label className="checkboxRow">
                  <input
                    checked={aiRuntimeTraceTruncationEnabled}
                    disabled={isSavingAiRuntimeConfig}
                    onChange={(event) => setAiRuntimeTraceTruncationEnabled(event.target.checked)}
                    type="checkbox"
                  />
                  <span>Truncar trazas de request/response (seguro)</span>
                </label>
                <p className="metaText">
                  Desactivalo para guardar trazas completas (puede aumentar peso y costo).
                </p>
                <p className="metaText">
                  Ultima actualizacion: {new Date(aiRuntimeConfig.updated_at).toLocaleString()} por{" "}
                  {aiRuntimeConfig.updated_by}
                </p>
                <div className="cardActions">
                  <button
                    disabled={isSavingAiRuntimeConfig}
                    onClick={() => void handleSaveAiRuntimeConfig()}
                    type="button"
                  >
                    {isSavingAiRuntimeConfig ? "Guardando..." : "Guardar configuracion IA"}
                  </button>
                </div>
              </article>
            </div>
          )}
        </section>
      ) : null}

      {showAdminPromptsPage ? (
        <section className="panel selectedPanel">
        <header className="panelHeader">
          <div>
            <h2>Administracion de prompts (global V1)</h2>
            <p>
              Primero se listan prompts IA (guardrails, identidad y tareas). Luego se agrupan
              consultas externas Tavily con sus prompts asociados.
            </p>
          </div>
          <button
            className="ghostButton"
            disabled={isLoadingPromptConfigs}
            onClick={() => setPromptConfigReloadToken((current) => current + 1)}
            type="button"
          >
            {isLoadingPromptConfigs ? "Actualizando..." : "Refrescar"}
          </button>
        </header>
        {isLoadingPromptConfigs ? (
          <p className="metaText">Cargando configuracion de prompts...</p>
        ) : promptConfigs.length === 0 ? (
          <p className="metaText">No hay flujos de prompts configurados.</p>
        ) : (
          <>
          {(() => {
            const configByFlow = new Map(
              orderedPromptConfigs.map((config) => [config.flow_key, config] as const)
            );
            const renderPromptConfigCard = (config: PromptConfig) => {
              const draft = promptConfigDrafts[config.flow_key] ?? {
                template_text: config.template_text,
                target_sources_input: config.target_sources.join("\n"),
                is_active: config.is_active
              };
              const isSaving = savingPromptFlowKey === config.flow_key;
              const isExpanded = Boolean(expandedPromptVersions[config.flow_key]);
              const isLoadingVersions = loadingPromptVersionsFlowKey === config.flow_key;
              const isRollingBack = rollingBackPromptFlowKey === config.flow_key;
              const versions = promptVersionsByFlow[config.flow_key] ?? [];
              const isSourceFlow = PROMPT_SOURCE_FLOW_KEYS.has(config.flow_key);
              return (
                <article className="manualCard promptConfigCard" key={config.flow_key}>
                  <div className="promptConfigHeader">
                    <div>
                      <p className="chatRole">
                        {PROMPT_FLOW_LABELS[config.flow_key] ?? config.flow_key}
                      </p>
                      <p className="metaText">flow_key: {config.flow_key}</p>
                    </div>
                    <label className="checkboxRow promptConfigToggle">
                      <input
                        checked={draft.is_active}
                        disabled={isSaving}
                        onChange={(event) =>
                          handlePromptDraftChange(config.flow_key, {
                            is_active: event.target.checked
                          })
                        }
                        type="checkbox"
                      />
                      <span>Configuracion activa</span>
                    </label>
                  </div>
                  <div className={isSourceFlow ? "promptConfigCardSplit" : "promptConfigCardStack"}>
                    <div className="promptConfigColumn">
                      <label className="field">
                        Plantilla de prompt
                        <textarea
                          className="promptTextarea"
                          disabled={isSaving}
                          onChange={(event) =>
                            handlePromptDraftChange(config.flow_key, {
                              template_text: event.target.value
                            })
                          }
                          rows={5}
                          value={draft.template_text}
                        />
                      </label>
                    </div>
                    <div className="promptConfigColumn promptConfigSide">
                      {isSourceFlow ? (
                        <label className="field">
                          Fuentes objetivo (coma o salto de linea)
                          <textarea
                            className="promptTextarea"
                            disabled={isSaving}
                            onChange={(event) =>
                              handlePromptDraftChange(config.flow_key, {
                                target_sources_input: event.target.value
                              })
                            }
                            rows={5}
                            value={draft.target_sources_input}
                          />
                          <small className="metaText">
                            Opcional: puedes dejarlo vacio para buscar sin restringir fuentes.
                          </small>
                        </label>
                      ) : (
                        <p className="metaText">Este flujo no usa fuentes objetivo.</p>
                      )}
                    </div>
                  </div>
                  <div className="promptConfigFooter">
                    <p className="metaText">
                      Ultima actualizacion: {new Date(config.updated_at).toLocaleString()} por{" "}
                      {config.updated_by}
                    </p>
                    <div className="cardActions">
                      <button
                        disabled={isSaving}
                        onClick={() => void handleSavePromptConfig(config.flow_key)}
                        type="button"
                      >
                        {isSaving ? "Guardando..." : "Guardar configuracion"}
                      </button>
                      <button
                        disabled={isSaving || isRollingBack}
                        onClick={() => handleTogglePromptVersions(config.flow_key)}
                        type="button"
                      >
                        {isExpanded ? "Ocultar versiones" : "Ver versiones"}
                      </button>
                    </div>
                  </div>
                  {isExpanded ? (
                    <div className="chatList">
                      {isLoadingVersions ? (
                        <p className="metaText">Cargando historial...</p>
                      ) : versions.length === 0 ? (
                        <p className="metaText">Sin versiones registradas para este flujo.</p>
                      ) : (
                        versions.map((version) => (
                          <article
                            className="chatBubble chatBubbleAssistant"
                            key={version.version_id}
                          >
                            <p className="chatRole">
                              version: {version.version_id}
                            </p>
                            <p className="metaText">
                              creada: {formatAiRunTimestamp(version.created_at)} por{" "}
                              {version.created_by} · motivo: {version.reason}
                            </p>
                            <p className="metaText">
                              snapshot origen: {version.source_updated_by} ·{" "}
                              {formatAiRunTimestamp(version.source_updated_at)}
                            </p>
                            <details className="payloadDetails">
                              <summary>Ver template versionado</summary>
                              <pre className="payloadPre">{version.template_text}</pre>
                            </details>
                            {PROMPT_SOURCE_FLOW_KEYS.has(config.flow_key) ? (
                              <details className="payloadDetails">
                                <summary>Ver target_sources versionados</summary>
                                <pre className="payloadPre">
                                  {JSON.stringify(version.target_sources, null, 2)}
                                </pre>
                              </details>
                            ) : null}
                            <div className="cardActions">
                              <button
                                disabled={isRollingBack}
                                onClick={() =>
                                  void handleRollbackPromptConfig(
                                    config.flow_key,
                                    version.version_id
                                  )
                                }
                                type="button"
                              >
                                {isRollingBack
                                  ? "Restaurando..."
                                  : "Restaurar esta version"}
                              </button>
                            </div>
                          </article>
                        ))
                      )}
                    </div>
                  ) : null}
                </article>
              );
            };
            const moduleDefinitions = [
              {
                title: "Fit cultural",
                searchFlow: "search_culture_tavily",
                promptFlows: ["task_analyze_cultural_fit"]
              },
              {
                title: "Entrevista",
                searchFlow: "search_interview_tavily",
                promptFlows: ["task_interview_research_plan", "task_interview_brief"]
              },
              {
                title: "Busqueda de vacantes",
                searchFlow: "search_jobs_tavily",
                promptFlows: []
              }
            ];
            const modulePromptFlowSet = new Set(
              moduleDefinitions.flatMap((module) => module.promptFlows)
            );
            const promptOnlyConfigs = orderedPromptConfigs.filter(
              (config) =>
                !PROMPT_SOURCE_FLOW_KEYS.has(config.flow_key)
                && !modulePromptFlowSet.has(config.flow_key)
            );
            return (
              <>
                <div className="promptSectionHeader">
                  <h3>Prompts IA</h3>
                  <p className="metaText">
                    Guardrails, identidad y tareas de analisis, entrevista y postulacion.
                  </p>
                </div>
                <div className="promptConfigGrid promptConfigGridSingle">
                  {promptOnlyConfigs.map((config) => renderPromptConfigCard(config))}
                </div>
                <div className="promptSectionHeader">
                  <h3>Contexto externo (Tavily + prompts)</h3>
                  <p className="metaText">
                    Consultas de busqueda con sus prompts asociados por modulo.
                  </p>
                </div>
                <div className="promptModuleList">
                  {moduleDefinitions.map((module) => {
                    const searchConfig = configByFlow.get(module.searchFlow);
                    const promptConfigs = module.promptFlows
                      .map((flow) => configByFlow.get(flow))
                      .filter(Boolean) as PromptConfig[];
                    if (!searchConfig) {
                      return null;
                    }
                    return (
                      <section className="promptModule" key={module.searchFlow}>
                        <h4>{module.title}</h4>
                        <div className="promptModuleGrid">
                          <div className="promptModuleColumn">
                            {renderPromptConfigCard(searchConfig)}
                          </div>
                          <div className="promptModulePromptGrid">
                            {promptConfigs.length > 0 ? (
                              promptConfigs.map((config) => renderPromptConfigCard(config))
                            ) : (
                              <article className="manualCard promptConfigCard promptConfigEmpty">
                                <p className="metaText">
                                  No hay prompt asociado para este modulo.
                                </p>
                              </article>
                            )}
                          </div>
                        </div>
                      </section>
                    );
                  })}
                </div>
              </>
            );
          })()}
          </>
        )}
        </section>
      ) : null}

      {showProfilePage ? (
        <section className="panel selectedPanel">
        <h2>Candidato</h2>
        {selectedPerson ? (
          <div className="cvCard">
            <div className="profileSplitGrid">
              <article className="manualCard profileSectionCard">
                <label className="field">
                  Nombre completo
                  <input
                    disabled={isSavingProfile}
                    onChange={(event) => setProfileFullName(event.target.value)}
                    value={profileFullName}
                  />
                </label>
                <div className="manualRow">
                  <label className="field">
                    Ubicacion
                    <input
                      disabled={isSavingProfile}
                      onChange={(event) => setProfileLocation(event.target.value)}
                      value={profileLocation}
                    />
                  </label>
                  <label className="field">
                    Años de experiencia
                    <input
                      disabled={isSavingProfile}
                      max={80}
                      min={0}
                      onChange={(event) => setProfileYearsExperienceInput(event.target.value)}
                      type="number"
                      value={profileYearsExperienceInput}
                    />
                  </label>
                </div>
                <div className="manualRow">
                  <label className="field">
                    Expectativa salarial min
                    <input
                      disabled={isSavingProfile}
                      min={0}
                      onChange={(event) => setProfileSalaryMinInput(event.target.value)}
                      placeholder="Minimo"
                      type="number"
                      value={profileSalaryMinInput}
                    />
                  </label>
                  <label className="field">
                    Expectativa salarial max
                    <input
                      disabled={isSavingProfile}
                      min={0}
                      onChange={(event) => setProfileSalaryMaxInput(event.target.value)}
                      placeholder="Maximo"
                      type="number"
                      value={profileSalaryMaxInput}
                    />
                  </label>
                </div>
                <div className="manualRow">
                  <label className="field">
                    Moneda
                    <select
                      disabled={isSavingProfile}
                      onChange={(event) => setProfileSalaryCurrency(event.target.value)}
                      value={profileSalaryCurrency}
                    >
                      <option value="">Sin definir</option>
                      {SALARY_CURRENCIES.map((currency) => (
                        <option key={currency} value={currency}>
                          {currency}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    Periodo
                    <select
                      disabled={isSavingProfile}
                      onChange={(event) => setProfileSalaryPeriod(event.target.value)}
                      value={profileSalaryPeriod}
                    >
                      <option value="">Sin definir</option>
                      {SALARY_PERIODS.map((period) => (
                        <option key={period.value} value={period.value}>
                          {period.label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="field">
                  Roles objetivo (coma o salto de linea)
                  <textarea
                    disabled={isSavingProfile}
                    onChange={(event) => setProfileTargetRolesInput(event.target.value)}
                    rows={2}
                    value={profileTargetRolesInput}
                  />
                </label>
                <label className="field">
                  Skills (coma o salto de linea)
                  <textarea
                    disabled={isSavingProfile}
                    onChange={(event) => setProfileSkillsInput(event.target.value)}
                    rows={2}
                    value={profileSkillsInput}
                  />
                </label>
                <div className="cardActions">
                  <button
                    className="primaryButton buttonCompact"
                    disabled={isSavingProfile}
                    onClick={() => void handleSaveProfile()}
                    type="button"
                  >
                    {isSavingProfile ? "Guardando..." : "Guardar perfil"}
                  </button>
                </div>
              </article>

              <article className="manualCard profileSectionCard">
                <h3 className="subheading subheadingCompact">
                  Condiciones de trabajo y preferencias culturales
                </h3>
                <div className="cultureGrid cultureGridCompact">
                  {CULTURAL_FIELDS.map((field) => {
                    const value = culturePreferencesState[field.id] ?? {
                      enabled: false,
                      selected_values: [],
                      criticality: "normal"
                    };
                    const selectedCount = value.selected_values.length;
                    return (
                      <article className="manualCard cultureFieldCard" key={field.id}>
                        <p className="chatRole">{field.label}</p>
                        <div className="optionList optionListCompact">
                          {field.options.map((option) => (
                            <label
                              className="checkboxRow checkboxRowCompact"
                              key={`${field.id}-${option.value}`}
                            >
                              <input
                                checked={value.selected_values.includes(option.value)}
                                disabled={isSavingCulturePreferences}
                                onChange={(event) =>
                                  handleToggleCulturalOption(
                                    field.id,
                                    option.value,
                                    event.target.checked
                                  )
                                }
                                type="checkbox"
                              />
                              <span>{option.label}</span>
                            </label>
                          ))}
                        </div>
                        <div className="cultureFieldFooter">
                          {selectedCount > 0 ? (
                            <p className="metaText">{selectedCount} opcion(es) seleccionada(s)</p>
                          ) : null}
                        </div>
                      </article>
                    );
                  })}
                </div>
                <label className="field">
                  Notas abiertas sobre cultura y condiciones laborales
                  <textarea
                    disabled={isSavingCulturePreferences}
                    onChange={(event) => setCulturePreferencesNotes(event.target.value)}
                    rows={3}
                    value={culturePreferencesNotes}
                  />
                </label>
                <div className="cardActions">
                  <button
                    className="primaryButton buttonCompact"
                    disabled={isSavingCulturePreferences}
                    onClick={() => void handleSaveCulturePreferences()}
                    type="button"
                  >
                    {isSavingCulturePreferences ? "Guardando..." : "Guardar preferencias"}
                  </button>
                </div>
              </article>
            </div>
          </div>
        ) : (
          <p className="metaText">
            No hay perfil seleccionado. Elige uno para continuar.
          </p>
        )}
        </section>
      ) : null}
      {showProfilePage ? (
        <section className="panel selectedPanel">
        <header className="panelHeader">
          <div>
            <h2>CV</h2>
            <p>
              {activeCv
                ? "Resumen y vista previa del CV activo."
                : "Sube el CV para enriquecer el analisis y las respuestas."}
            </p>
          </div>
          {activeCv ? (
            <div className="cardActions">
              <button
                className={isCvUploadFormOpen ? "activeButton" : ""}
                onClick={() =>
                  setIsCvUploadFormOpen((current) => !current)
                }
                type="button"
              >
                {isCvUploadFormOpen ? "Ocultar carga" : "Reemplazar CV"}
              </button>
            </div>
          ) : null}
        </header>
        {isLoadingCv ? (
          <p className="metaText">Consultando CV activo...</p>
        ) : activeCv ? (
          <div className="cvCard">
            <article className="manualCard cvSummaryCard">
              <p className="metaText">
                Archivo: <strong>{activeCv.source_filename}</strong>
              </p>
              <div className="metaChips">
                <span className="metaChip">Extraccion: {activeCv.extraction_status}</span>
                <span className="metaChip">Formato: {activeCv.extraction_format}</span>
                <span className="metaChip">
                  Vector: {activeCv.vector_index_status} · chunks {activeCv.vector_chunks_indexed}
                </span>
                <span className="metaChip">
                  Chunking: {activeCv.vector_chunking_strategy} ({activeCv.vector_chunking_version})
                </span>
                <span className="metaChip">Fuente vector: {activeCv.vector_source_format}</span>
                <span className="metaChip">
                  Texto: {activeCv.text_length} caracteres
                  {activeCv.text_truncated ? " (truncado)" : ""}
                </span>
              </div>
              <article className="chatBubble chatBubbleAssistant cvPreviewSection">
                <p className="chatRole">Vista previa estructurada (Markdown)</p>
                <MarkdownContent
                  className={
                    isCvPreviewExpanded
                      ? "chatContent cvPreviewText resultBlockMarkdown"
                      : "chatContent cvPreviewText resultBlockMarkdown cvPreviewTextCollapsed"
                  }
                  content={
                    isCvPreviewExpanded
                    ? cvExpandedText || "No se obtuvo texto util del archivo."
                    : cvPreviewShortText || "No se obtuvo texto util del archivo."
                  }
                />
                {isCvPreviewExpanded && isLoadingCvFullText ? (
                  <p className="metaText">Cargando texto completo...</p>
                ) : null}
                {hasMoreCvPreview ? (
                  <div className="cardActions">
                    <button
                      className="ghostButton buttonCompact"
                      disabled={isLoadingCvFullText}
                      onClick={() => void handleToggleCvPreview()}
                      type="button"
                    >
                      {isCvPreviewExpanded ? "Ver menos" : "Ver mas"}
                    </button>
                  </div>
                ) : null}
              </article>
            </article>
          </div>
        ) : (
          <p className="metaText">
            No hay CV activo para este perfil. Puedes operar sin CV y cargarlo despues.
          </p>
        )}
        {isCvUploadFormOpen ? (
          <>
            <form className="cvForm cvFormCompact" onSubmit={handleUploadCv}>
              <label className="ghostButton buttonCompact filePickerButton" htmlFor="cv-upload-input">
                Seleccionar archivo
              </label>
              <input
                className="filePickerInput"
                accept=".pdf,.txt,.md"
                disabled={!selectedPersonId || isUploadingCv}
                id="cv-upload-input"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedCvFile(file);
                }}
                type="file"
              />
              <button
                className="primaryButton buttonCompact"
                disabled={!selectedPersonId || !selectedCvFile || isUploadingCv}
                type="submit"
              >
                {isUploadingCv ? "Cargando..." : activeCv ? "Reemplazar CV" : "Subir CV"}
              </button>
            </form>
            <p className="metaText">
              Archivo para subir:{" "}
              <strong>{selectedCvFile ? selectedCvFile.name : "Ninguno seleccionado"}</strong>
            </p>
          </>
        ) : null}
        </section>
      ) : null}
      {showConversationSection ? (
        <>
          <button
            className="chatDrawerToggle"
            onClick={() => setIsChatDrawerOpen((current) => !current)}
            type="button"
          >
            {isChatDrawerOpen ? "Cerrar chat" : "Chat IA"}
          </button>
          <aside
            aria-hidden={!isChatDrawerOpen}
            className={isChatDrawerOpen ? "chatDrawer chatDrawerOpen" : "chatDrawer"}
          >
            <header className="chatDrawerHeader">
              <div>
                <p className="eyebrow">Asistente IA</p>
                <h2>Conversacion contextual</h2>
                <p className="metaText">
                  {selectedPerson ? selectedPerson.full_name : "Sin persona activa"}
                </p>
              </div>
              <button
                className="ghostButton"
                onClick={() => setIsChatDrawerOpen(false)}
                type="button"
              >
                Cerrar
              </button>
            </header>
            <div className="chatDrawerBody">
              {isConversationLoading ? (
                <p className="metaText">Cargando conversacion...</p>
              ) : (
                <div className="chatList">
                  {(conversation?.messages ?? []).length === 0 && !isSendingMessage ? (
                    <p className="metaText">No hay mensajes aun para este perfil.</p>
                  ) : (
                    conversation?.messages.map((message) => (
                      <article
                        className={
                          message.role === "user"
                            ? "chatBubble chatBubbleUser"
                            : "chatBubble chatBubbleAssistant"
                        }
                        key={message.message_id}
                      >
                        <p className="chatRole">{message.role === "user" ? "Tutor" : "Asistente"}</p>
                        <p className="chatContent">{message.content}</p>
                      </article>
                    ))
                  )}
                  {isSendingMessage ? (
                    <article className="chatBubble chatBubbleAssistant">
                      <p className="chatRole">Asistente (SSE)</p>
                      <p className="chatContent">
                        {streamingAssistantText || "Procesando respuesta..."}
                      </p>
                    </article>
                  ) : null}
                </div>
              )}
            </div>
            <form className="chatForm chatDrawerForm" onSubmit={handleSendMessage}>
              <input
                disabled={!selectedPersonId || isSendingMessage}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="Escribe un mensaje para este perfil..."
                value={chatInput}
              />
              <button
                className="primaryButton"
                disabled={!selectedPersonId || isSendingMessage || !chatInput.trim()}
                type="submit"
              >
                {isSendingMessage ? "Enviando..." : "Enviar"}
              </button>
            </form>
          </aside>
        </>
      ) : null}
      {showOpportunitiesPage ? (
        <section className="panel selectedPanel">
        <h2>Descubrimiento de vacantes</h2>
        <div className="opportunityModeTabs" role="tablist" aria-label="Modo de descubrimiento">
          <button
            className={
              opportunityDiscoveryMode === "manual"
                ? "opportunityModeTab opportunityModeTabActive"
                : "opportunityModeTab"
            }
            aria-selected={opportunityDiscoveryMode === "manual"}
            onClick={() => setOpportunityDiscoveryMode("manual")}
            role="tab"
            type="button"
          >
            Carga manual
          </button>
          <button
            className={
              opportunityDiscoveryMode === "search"
                ? "opportunityModeTab opportunityModeTabActive"
                : "opportunityModeTab"
            }
            aria-selected={opportunityDiscoveryMode === "search"}
            onClick={() => setOpportunityDiscoveryMode("search")}
            role="tab"
            type="button"
          >
            Búsqueda
          </button>
        </div>
        {opportunityDiscoveryMode === "search" ? (
          <>
            <form className="chatForm searchComposerForm" onSubmit={handleSearch}>
              <label className="field">
                Buscar oportunidades, roles o empresas
                <input
                  disabled={!selectedPersonId || isSearching}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Product Designer, UX Researcher, Bogota..."
                  value={searchQuery}
                />
              </label>
              {searchRoleKeywords.length > 0 ? (
                <article className="manualCard searchRoleComposer">
                  <div className="searchRoleHeader">
                    <div className="metaChips roleChipGroup">
                      {searchRoleKeywords.map((role) => {
                        const selected = hasRoleToken(searchQuery, role);
                        return (
                          <button
                            className={selected ? "metaChip metaChipActive" : "metaChip"}
                            key={`search-role-${role}`}
                            onClick={() => handleToggleSearchRole(role)}
                            type="button"
                          >
                            {role}
                          </button>
                        );
                      })}
                    </div>
                    <div className="cardActions searchRoleActions">
                      <button
                        className="ghostButton miniButton"
                        disabled={!selectedPersonId || searchRoleKeywords.length === 0}
                        onClick={handleSelectAllSearchRoles}
                        type="button"
                      >
                        Seleccionar todas
                      </button>
                      <button
                        className="ghostButton miniButton"
                        disabled={!selectedPersonId || selectedSearchRoleCount === 0}
                        onClick={handleClearSearchRoles}
                        type="button"
                      >
                        Limpiar seleccion
                      </button>
                    </div>
                  </div>
                </article>
              ) : null}
              <div className="searchActionRow">
                <button
                  className="primaryButton searchSubmitButton"
                  disabled={!selectedPersonId || isSearching || !searchQuery.trim()}
                  type="submit"
                >
                  {isSearching ? "Buscando..." : "Buscar"}
                </button>
              </div>
            </form>
            {searchWarnings.length > 0 ? (
              <p className="metaText">Avisos: {searchWarnings.join(" | ")}</p>
            ) : null}
            <div className="chatList">
              {searchResults.length === 0 ? (
                <p className="metaText">No hay resultados de busqueda recientes.</p>
              ) : (
                searchResults.map((result) => (
                  <article
                    className={
                      selectedSearchResultId === result.search_result_id
                        ? "chatBubble chatBubbleAssistant searchResultCard searchResultCardActive"
                        : "chatBubble chatBubbleAssistant searchResultCard"
                    }
                    key={result.search_result_id}
                  >
                    <p className="chatRole">{result.source_provider}</p>
                    <p className="chatContent">{result.title}</p>
                    <div className="metaChips">
                      <span className="metaChip">{result.company || "Empresa no identificada"}</span>
                      <span className="metaChip">{result.location || "Ubicacion no especificada"}</span>
                    </div>
                    <p className="metaText">
                      <ExternalUrlText url={result.source_url} />
                    </p>
                    <p className="metaText">{result.snippet}</p>
                    <div className="cardActions">
                      <button
                        className={
                          selectedSearchResultId === result.search_result_id ? "activeButton" : ""
                        }
                        onClick={() =>
                          setSelectedSearchResultId((current) =>
                            current === result.search_result_id ? null : result.search_result_id
                          )
                        }
                        type="button"
                      >
                        {selectedSearchResultId === result.search_result_id
                          ? "Cerrar detalle"
                          : "Abrir detalle"}
                      </button>
                      <button
                        disabled={savingResultId === result.search_result_id}
                        onClick={() => void handleSaveSearchResult(result)}
                        type="button"
                      >
                        {savingResultId === result.search_result_id
                          ? "Guardando..."
                          : "Guardar como oportunidad"}
                      </button>
                    </div>
                    {selectedSearchResultId === result.search_result_id ? (
                      <article className="inlineDetailCard">
                        <p className="chatRole">Detalle (no persistido)</p>
                        <p className="metaText">
                          Proveedor: {result.source_provider} · Empresa:{" "}
                          {result.company || "No identificada"} · Ubicacion:{" "}
                          {result.location || "No especificada"}
                        </p>
                        <p className="metaText">
                          URL: <ExternalUrlText noValueText="No disponible" url={result.source_url} />
                        </p>
                        <article className="chatBubble chatBubbleAssistant">
                          <p className="chatRole">Snippet</p>
                          <p className="chatContent">{result.snippet || "Sin snippet"}</p>
                        </article>
                        <article className="chatBubble chatBubbleUser">
                          <p className="chatRole">Payload normalizado</p>
                          <pre className="payloadPre">
                            {JSON.stringify(result.normalized_payload, null, 2)}
                          </pre>
                        </article>
                        <p className="metaText">
                          Capturado: {new Date(result.captured_at).toLocaleString()}
                        </p>
                      </article>
                    ) : null}
                  </article>
                ))
              )}
            </div>
            {searchProviderStatus.length > 0 ? (
              <details className="collapsibleSection providerStatusPanel">
                <summary>Log tecnico de proveedores (ultima busqueda)</summary>
                <div className="providerStatusList">
                  {searchProviderStatus.map((status) => {
                    const diagnostic = buildSearchProviderDiagnostic(status);
                    const providerLabel =
                      SEARCH_PROVIDER_LABELS[status.provider_key] ?? status.provider_key;
                    return (
                      <article
                        className="providerStatusItem"
                        key={`provider-status-${status.provider_key}`}
                      >
                        <p className="providerStatusTitle">{providerLabel}</p>
                        <pre className="providerStatusLog">{`${status.provider_key} | ${diagnostic.statusLabel} | results=${status.results_count} | reason=${status.reason}`}</pre>
                        {status.query_truncated ? (
                          <p className="providerStatusHint">query_truncated=true</p>
                        ) : null}
                        {diagnostic.rawReason ? (
                          <details className="payloadDetails">
                            <summary>Detalle tecnico</summary>
                            <pre className="providerStatusLog providerStatusLogMuted">
                              {diagnostic.rawReason}
                            </pre>
                          </details>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              </details>
            ) : null}
          </>
        ) : (
          <form className="manualCard opportunityManualPanel" onSubmit={handleImportByUrl}>
            <p className="chatRole">Carga manual de oportunidades</p>
            <input
              disabled={!selectedPersonId || isImportingUrl}
              onChange={(event) => setManualUrl(event.target.value)}
              placeholder="https://sitio.com/vacante"
              value={manualUrl}
            />
            <input
              disabled={!selectedPersonId || isImportingUrl}
              onChange={(event) => setManualUrlTitle(event.target.value)}
              placeholder="Titulo (opcional)"
              value={manualUrlTitle}
            />
            <div className="manualRow">
              <input
                disabled={!selectedPersonId || isImportingUrl}
                onChange={(event) => setManualUrlCompany(event.target.value)}
                placeholder="Empresa (opcional)"
                value={manualUrlCompany}
              />
              <input
                disabled={!selectedPersonId || isImportingUrl}
                onChange={(event) => setManualUrlLocation(event.target.value)}
                placeholder="Ubicacion (opcional)"
                value={manualUrlLocation}
              />
            </div>
            <textarea
              disabled={!selectedPersonId || isImportingUrl}
              onChange={(event) => setManualUrlRawText(event.target.value)}
              placeholder="Descripcion o snapshot textual (obligatorio)"
              rows={3}
              value={manualUrlRawText}
            />
            <p className="metaText">
              Requerido: describe la vacante (minimo 8 caracteres).
            </p>
            <button
              className="primaryButton"
              disabled={
                !selectedPersonId ||
                isImportingUrl ||
                !manualUrl.trim() ||
                manualUrlRawText.trim().length < 8
              }
              type="submit"
            >
              {isImportingUrl ? "Importando..." : "Cargar"}
            </button>
          </form>
        )}
        <h3 className="subheading savedOpportunitiesHeading">Oportunidades guardadas</h3>
        {isLoadingOpportunities ? (
          <p className="metaText">Cargando oportunidades...</p>
        ) : savedOpportunities.length === 0 ? (
          <p className="metaText">No hay oportunidades guardadas para este perfil.</p>
        ) : (
          <div className="chatList">
            {savedOpportunities.map((item) => {
              const isExpanded = expandedSavedOpportunityPreview[item.opportunity_id] ?? false;
              const opportunityUrl = toExternalUrl(item.source_url);
              const descriptionPreview = buildContentLinePreview(
                item.snapshot_raw_text ?? "",
                2,
                isExpanded
              );
              return (
                <article
                  className="chatBubble chatBubbleUser savedOpportunityCard"
                  key={item.opportunity_id}
                >
                  <p className="chatRole savedOpportunityStatus">{item.status.toUpperCase()}</p>
                  <p className="chatContent savedOpportunityTitle">{item.title}</p>
                  <div className="metaChips">
                    <span className="metaChip">{item.company || "Empresa no identificada"}</span>
                    <span className="metaChip">{item.location || "Ubicacion no especificada"}</span>
                    <span className={getOpportunityOriginChipClass(item.source_type)}>
                      {getOpportunityOriginLabel(item.source_type)}
                    </span>
                  </div>
                  {descriptionPreview.previewText ? (
                    <p className="savedOpportunitySnippet">{descriptionPreview.previewText}</p>
                  ) : null}
                  <div className="savedOpportunityLinkRow">
                    <div className="savedOpportunityLinkExpandSlot">
                      {descriptionPreview.hasOverflow ? (
                        <button
                          aria-label={isExpanded ? "Contraer descripcion" : "Expandir descripcion"}
                          className="iconOnlyButton"
                          onClick={(event) => {
                            event.stopPropagation();
                            setExpandedSavedOpportunityPreview((current) => ({
                              ...current,
                              [item.opportunity_id]: !isExpanded
                            }));
                          }}
                          title={isExpanded ? "Contraer" : "Ver mas"}
                          type="button"
                        >
                          <ExpandCollapseIcon expanded={isExpanded} />
                        </button>
                      ) : null}
                    </div>
                    <div className="savedOpportunityLinkActions">
                      {opportunityUrl ? (
                        <a
                          className="savedOpportunityLinkButton"
                          href={opportunityUrl}
                          onClick={(event) => event.stopPropagation()}
                          rel="noreferrer"
                          target="_blank"
                        >
                          <span>Ver vacante</span>
                          <span aria-hidden="true">↗</span>
                        </a>
                      ) : (
                        <span className="savedOpportunityLinkUnavailable">URL no disponible</span>
                      )}
                      {opportunityUrl ? (
                        <button
                          aria-label="Copiar URL de la vacante"
                          className="iconOnlyButton savedOpportunityCopyButton"
                          onClick={(event) => {
                            event.stopPropagation();
                            void handleCopyOpportunityUrl(item.opportunity_id, item.source_url);
                          }}
                          title={copiedOpportunityUrlId === item.opportunity_id ? "Copiada" : "Copiar URL"}
                          type="button"
                        >
                          {copiedOpportunityUrlId === item.opportunity_id ? "✓" : "⧉"}
                        </button>
                      ) : null}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
        </section>
      ) : null}
      {showAnalysisPage ? (
        <section className="panel selectedPanel">
          <div
            className="analysisTopPanel"
          >
            <header className="analysisColumnHeader">
              <h3>Oportunidades guardadas</h3>
            </header>
            {isLoadingOpportunities ? (
              <p className="metaText">Cargando oportunidades...</p>
            ) : savedOpportunities.length === 0 ? (
              <p className="metaText">No hay oportunidades guardadas para este perfil.</p>
            ) : (
              <div className="analysisOpportunityList analysisOpportunityListTop">
                {savedOpportunities.map((item) => {
                  const isExpanded = expandedAnalysisOpportunityPreview[item.opportunity_id] ?? false;
                  const opportunityUrl = toExternalUrl(item.source_url);
                  const descriptionPreview = buildContentLinePreview(
                    item.snapshot_raw_text ?? "",
                    2,
                    isExpanded
                  );
                  return (
                    <div
                      className={
                        selectedOpportunityId === item.opportunity_id
                          ? "analysisOpportunityRow analysisOpportunityRowSelected"
                          : "analysisOpportunityRow"
                      }
                      data-analysis-row-id={item.opportunity_id}
                      key={`analysis-${item.opportunity_id}`}
                    >
                      <article
                        className={
                          selectedOpportunityId === item.opportunity_id
                            ? "savedOpportunityCard analysisOpportunityCard analysisOpportunityCardActive"
                            : "savedOpportunityCard analysisOpportunityCard"
                        }
                        onClick={() => handleSelectOpportunityCard(item.opportunity_id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            handleSelectOpportunityCard(item.opportunity_id);
                          }
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <p className="chatRole savedOpportunityStatus">{item.status.toUpperCase()}</p>
                        <p className="chatContent savedOpportunityTitle">{item.title}</p>
                        <div className="metaChips">
                          <span className="metaChip">{item.company || "Empresa no identificada"}</span>
                          <span className="metaChip">{item.location || "Ubicacion no especificada"}</span>
                          <span className={getOpportunityOriginChipClass(item.source_type)}>
                            {getOpportunityOriginLabel(item.source_type)}
                          </span>
                        </div>
                        {descriptionPreview.previewText ? (
                          <p className="savedOpportunitySnippet analysisOpportunitySnippet">
                            {descriptionPreview.previewText}
                          </p>
                        ) : null}
                        <div className="savedOpportunityLinkRow">
                          <div className="savedOpportunityLinkExpandSlot">
                            {descriptionPreview.hasOverflow ? (
                              <button
                                aria-label={isExpanded ? "Contraer descripcion" : "Expandir descripcion"}
                                className="iconOnlyButton"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  setExpandedAnalysisOpportunityPreview((current) => ({
                                    ...current,
                                    [item.opportunity_id]: !isExpanded
                                  }));
                                }}
                                title={isExpanded ? "Contraer" : "Ver mas"}
                                type="button"
                              >
                                <ExpandCollapseIcon expanded={isExpanded} />
                              </button>
                            ) : null}
                          </div>
                          <div className="savedOpportunityLinkActions">
                            {opportunityUrl ? (
                              <a
                                className="savedOpportunityLinkButton"
                                href={opportunityUrl}
                                onClick={(event) => event.stopPropagation()}
                                rel="noreferrer"
                                target="_blank"
                              >
                                <span>Ver vacante</span>
                                <span aria-hidden="true">↗</span>
                              </a>
                            ) : (
                              <span className="savedOpportunityLinkUnavailable">URL no disponible</span>
                            )}
                            {opportunityUrl ? (
                              <button
                                aria-label="Copiar URL de la vacante"
                                className="iconOnlyButton savedOpportunityCopyButton"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  void handleCopyOpportunityUrl(item.opportunity_id, item.source_url);
                                }}
                                title={copiedOpportunityUrlId === item.opportunity_id ? "Copiada" : "Copiar URL"}
                                type="button"
                              >
                                {copiedOpportunityUrlId === item.opportunity_id ? "✓" : "⧉"}
                              </button>
                            ) : null}
                          </div>
                        </div>
                      </article>
                      {selectedOpportunityId === item.opportunity_id ? (
                        <div className="analysisDetailInlineMount" ref={setAnalysisDetailMountNode} />
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {selectedOpportunity && analysisDetailMountNode
            ? createPortal(
          <div
            className={
              isContextRailCollapsed
                ? "analysisBottomGrid analysisBottomGridCollapsed"
                : "analysisBottomGrid"
            }
          >
            <div className="analysisCenterColumn">
              <header className="analysisColumnHeader">
                <div className="analysisCenterHeader">
                  <h3>
                    Oportunidad activa:{" "}
                    {selectedOpportunity ? selectedOpportunity.title : "sin seleccionar"}
                  </h3>
                  {selectedOpportunity ? (
                    <p className="metaText analysisOpportunityMeta">
                      Estado: {opportunityStatus} · Notas: {opportunityNotes.trim().length}
                    </p>
                  ) : null}
                </div>
                {isContextRailCollapsed ? (
                  <button
                    aria-label="Mostrar contexto de historial y trazas"
                    className="iconOnlyButton contextRailToggleButton contextRailToggleButtonCollapsed hasTooltip"
                    data-tooltip="Mostrar contexto"
                    onClick={() => setIsContextRailCollapsed(false)}
                    title="Mostrar contexto"
                    type="button"
                  >
                    <ContextPanelIcon />
                  </button>
                ) : null}
              </header>

              {selectedOpportunity ? (
                <>
                  <article className="manualCard analysisResultsPanel">
                    <h3 className="subheading subheadingCompact">Resultados</h3>
                    <div className="opportunityModeTabs opportunityModeTabsCompact">
                      <button
                        className={
                          resultsPanelTab === "analysis"
                            ? "opportunityModeTab opportunityModeTabActive"
                            : "opportunityModeTab"
                        }
                        onClick={() => handleSwitchResultsTab("analysis")}
                        type="button"
                      >
                        Análisis
                      </button>
                      <button
                        className={
                          resultsPanelTab === "artifacts"
                            ? "opportunityModeTab opportunityModeTabActive"
                            : "opportunityModeTab"
                        }
                        onClick={() => handleSwitchResultsTab("artifacts")}
                        type="button"
                      >
                        Postulación
                      </button>
                    </div>

                    {resultsPanelTab === "analysis" ? (
                      <>
                        <div className="analysisResultSubTabsWrap">
                          <p className="analysisSubTabHint">Bloques de análisis</p>
                          <div
                            aria-label="Bloques de análisis"
                            className="opportunityModeTabs opportunityModeTabsCompact opportunityModeTabsWrap"
                            role="tablist"
                          >
                            {ANALYSIS_MENU_BLOCKS.map((item) => (
                              <button
                                aria-selected={selectedResultBlockId === item.id}
                                className={
                                  selectedResultBlockId === item.id
                                    ? "opportunityModeTab opportunityModeTabActive"
                                    : "opportunityModeTab"
                                }
                                key={item.id}
                                onClick={() => handleSelectResultBlock(item.id)}
                                role="tab"
                                type="button"
                              >
                                {item.label}
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="resultBlockList">
                          <article
                          className={
                            selectedResultBlockId !== "analysis_profile_match"
                              ? "resultBlockCard resultBlockCardHidden"
                              : selectedResultBlockId === "analysis_profile_match"
                              ? "resultBlockCard resultBlockCardActive"
                              : "resultBlockCard"
                          }
                          onClick={() => handleSelectResultBlock("analysis_profile_match")}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              handleSelectResultBlock("analysis_profile_match");
                            }
                          }}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="resultBlockTop">
                            <div>
                              <p className="chatRole">{BLOCK_LABEL_BY_ID.analysis_profile_match}</p>
                              <p className="metaText">
                                {profileRun
                                  ? `Generado · ${formatAiRunTimestamp(profileRun.updated_at)}`
                                  : "Sin generar"}
                              </p>
                              {profilePromptBadge ? (
                                <span
                                  className="promptBadge"
                                  title={profilePromptBadge.tooltip}
                                >
                                  {profilePromptBadge.label}
                                </span>
                              ) : null}
                            </div>
                            <div className="cardActions">
                              {profileRun ? (
                                <button
                                  aria-label="Recalcular alineacion perfil-vacante"
                                  className="iconOnlyButton"
                                  disabled={isAnalyzingProfile}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handleAnalyzeProfileMatch(
                                          selectedOpportunity.opportunity_id,
                                          true
                                        )
                                      : undefined;
                                  }}
                                  title="Recalcular"
                                  type="button"
                                >
                                  {isAnalyzingProfile ? <SpinnerIcon /> : "↻"}
                                </button>
                              ) : (
                                <button
                                  aria-label="Generar alineacion perfil-vacante"
                                  className="iconOnlyButton"
                                  disabled={isAnalyzingProfile}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handleAnalyzeProfileMatch(
                                          selectedOpportunity.opportunity_id
                                        )
                                      : undefined;
                                  }}
                                  title="Generar"
                                  type="button"
                                >
                                  {isAnalyzingProfile ? <SpinnerIcon /> : "▶"}
                                </button>
                              )}
                            </div>
                          </div>
                          {profileRuns.length > 1 ? (
                            <div className="resultBlockPager">
                              <button
                                className="ghostButton compactActionButton"
                                disabled={getCurrentRunIndexForBlock("analysis_profile_match") === 0}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("analysis_profile_match", -1);
                                }}
                                type="button"
                              >
                                ◀
                              </button>
                              <span className="metaText">
                                {getCurrentRunIndexForBlock("analysis_profile_match") + 1}/
                                {profileRuns.length}
                              </span>
                              <button
                                className="ghostButton compactActionButton"
                                disabled={
                                  getCurrentRunIndexForBlock("analysis_profile_match") >=
                                  profileRuns.length - 1
                                }
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("analysis_profile_match", 1);
                                }}
                                type="button"
                              >
                                ▶
                              </button>
                            </div>
                          ) : null}
                          {profilePreview.previewText ? (
                            <MarkdownContent
                              className="chatContent resultBlockContent resultBlockMarkdown"
                              content={profilePreview.previewText}
                            />
                          ) : null}
                          {profileContent &&
                          (profilePreview.truncated ||
                            expandedResultBlocks.analysis_profile_match) ? (
                            <div className="cardActions resultBlockToggleRow">
                              <button
                                aria-label={
                                  expandedResultBlocks.analysis_profile_match
                                    ? "Contraer contenido"
                                    : "Expandir contenido"
                                }
                                className="iconOnlyButton"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleToggleResultBlockPreview("analysis_profile_match");
                                }}
                                title={
                                  expandedResultBlocks.analysis_profile_match
                                    ? "Contraer"
                                    : "Expandir"
                                }
                                type="button"
                              >
                                <ExpandCollapseIcon
                                  expanded={expandedResultBlocks.analysis_profile_match}
                                />
                              </button>
                            </div>
                          ) : null}
                          </article>

                          <article
                          className={
                            selectedResultBlockId !== "analysis_cultural_fit"
                              ? "resultBlockCard resultBlockCardHidden"
                              : selectedResultBlockId === "analysis_cultural_fit"
                              ? "resultBlockCard resultBlockCardActive"
                              : "resultBlockCard"
                          }
                          onClick={() => handleSelectResultBlock("analysis_cultural_fit")}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              handleSelectResultBlock("analysis_cultural_fit");
                            }
                          }}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="resultBlockTop">
                            <div>
                              <p className="chatRole">{BLOCK_LABEL_BY_ID.analysis_cultural_fit}</p>
                              <p className="metaText">
                                {culturalRun
                                  ? `Generado · ${formatAiRunTimestamp(culturalRun.updated_at)}`
                                  : "Sin generar"}
                              </p>
                              {culturalPromptBadge ? (
                                <span
                                  className="promptBadge"
                                  title={culturalPromptBadge.tooltip}
                                >
                                  {culturalPromptBadge.label}
                                </span>
                              ) : null}
                            </div>
                            <div className="cardActions">
                              {culturalRun ? (
                                <button
                                  aria-label="Recalcular fit cultural"
                                  className="iconOnlyButton"
                                  disabled={isAnalyzingCultural}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handleAnalyzeCulturalFit(
                                          selectedOpportunity.opportunity_id,
                                          true
                                        )
                                      : undefined;
                                  }}
                                  title="Recalcular"
                                  type="button"
                                >
                                  {isAnalyzingCultural ? <SpinnerIcon /> : "↻"}
                                </button>
                              ) : (
                                <button
                                  aria-label="Generar fit cultural"
                                  className="iconOnlyButton"
                                  disabled={isAnalyzingCultural}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handleAnalyzeCulturalFit(
                                          selectedOpportunity.opportunity_id
                                        )
                                      : undefined;
                                  }}
                                  title="Generar"
                                  type="button"
                                >
                                  {isAnalyzingCultural ? <SpinnerIcon /> : "▶"}
                                </button>
                              )}
                            </div>
                          </div>
                          {culturalRuns.length > 1 ? (
                            <div className="resultBlockPager">
                              <button
                                className="ghostButton compactActionButton"
                                disabled={getCurrentRunIndexForBlock("analysis_cultural_fit") === 0}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("analysis_cultural_fit", -1);
                                }}
                                type="button"
                              >
                                ◀
                              </button>
                              <span className="metaText">
                                {getCurrentRunIndexForBlock("analysis_cultural_fit") + 1}/
                                {culturalRuns.length}
                              </span>
                              <button
                                className="ghostButton compactActionButton"
                                disabled={
                                  getCurrentRunIndexForBlock("analysis_cultural_fit") >=
                                  culturalRuns.length - 1
                                }
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("analysis_cultural_fit", 1);
                                }}
                                type="button"
                              >
                                ▶
                              </button>
                            </div>
                          ) : null}
                          {culturalPreview.previewText ? (
                            <p className="chatContent resultBlockContent">{culturalPreview.previewText}</p>
                          ) : null}
                          {culturalConfidenceView ? (
                            <p className="metaText">
                              Confianza: <strong>{culturalConfidenceView}</strong>
                            </p>
                          ) : null}
                          {culturalWarningsView.length > 0 ? (
                            <p className="metaText">
                              Advertencias: {culturalWarningsView.length}
                            </p>
                          ) : null}
                          {culturalSignalsView.length > 0 ? (
                            <details
                              className="resultSourcesDetails"
                              onClick={(event) => event.stopPropagation()}
                            >
                              <summary>Fuentes referenciadas ({culturalSignalsView.length})</summary>
                              <ul className="resultSourcesList">
                                {culturalSignalsView.slice(0, 8).map((item, index) => (
                                  <li className="resultSourcesItem" key={`${item.source_url}-${index}`}>
                                    <ExternalUrlText
                                      noValueText={item.title || "Fuente sin URL"}
                                      url={item.source_url}
                                    />
                                  </li>
                                ))}
                              </ul>
                            </details>
                          ) : null}
                          {culturalContent &&
                          (culturalPreview.truncated ||
                            expandedResultBlocks.analysis_cultural_fit) ? (
                            <div className="cardActions resultBlockToggleRow">
                              <button
                                aria-label={
                                  expandedResultBlocks.analysis_cultural_fit
                                    ? "Contraer contenido"
                                    : "Expandir contenido"
                                }
                                className="iconOnlyButton"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleToggleResultBlockPreview("analysis_cultural_fit");
                                }}
                                title={
                                  expandedResultBlocks.analysis_cultural_fit
                                    ? "Contraer"
                                    : "Expandir"
                                }
                                type="button"
                              >
                                <ExpandCollapseIcon
                                  expanded={expandedResultBlocks.analysis_cultural_fit}
                                />
                              </button>
                            </div>
                          ) : null}
                          </article>

                        <article
                          className={
                            selectedResultBlockId !== "analysis_interview_brief"
                              ? "resultBlockCard resultBlockCardHidden"
                              : selectedResultBlockId === "analysis_interview_brief"
                              ? "resultBlockCard resultBlockCardActive"
                              : "resultBlockCard"
                          }
                          onClick={() => handleSelectResultBlock("analysis_interview_brief")}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              handleSelectResultBlock("analysis_interview_brief");
                            }
                          }}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="resultBlockTop">
                            <div>
                              <p className="chatRole">{BLOCK_LABEL_BY_ID.analysis_interview_brief}</p>
                              <p className="metaText">
                                {interviewRun
                                  ? `Generado · ${formatAiRunTimestamp(interviewRun.updated_at)}`
                                  : "Sin generar"}
                              </p>
                              {interviewPromptBadge ? (
                                <span
                                  className="promptBadge"
                                  title={interviewPromptBadge.tooltip}
                                >
                                  {interviewPromptBadge.label}
                                </span>
                              ) : null}
                            </div>
                            <div className="cardActions">
                              {interviewRun ? (
                                <button
                                  aria-label="Recalcular brief de entrevista"
                                  className="iconOnlyButton"
                                  disabled={isInterviewing}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handleInterviewBrief(
                                          selectedOpportunity.opportunity_id,
                                          true
                                        )
                                      : undefined;
                                  }}
                                  title="Recalcular"
                                  type="button"
                                >
                                  {isInterviewing ? <SpinnerIcon /> : "↻"}
                                </button>
                              ) : (
                                <button
                                  aria-label="Generar brief de entrevista"
                                  className="iconOnlyButton"
                                  disabled={isInterviewing}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handleInterviewBrief(
                                          selectedOpportunity.opportunity_id
                                        )
                                      : undefined;
                                  }}
                                  title="Generar"
                                  type="button"
                                >
                                  {isInterviewing ? <SpinnerIcon /> : "▶"}
                                </button>
                              )}
                            </div>
                          </div>
                          {interviewRuns.length > 1 ? (
                            <div className="resultBlockPager">
                              <button
                                className="ghostButton compactActionButton"
                                disabled={getCurrentRunIndexForBlock("analysis_interview_brief") === 0}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("analysis_interview_brief", -1);
                                }}
                                type="button"
                              >
                                ◀
                              </button>
                              <span className="metaText">
                                {getCurrentRunIndexForBlock("analysis_interview_brief") + 1}/
                                {interviewRuns.length}
                              </span>
                              <button
                                className="ghostButton compactActionButton"
                                disabled={
                                  getCurrentRunIndexForBlock("analysis_interview_brief") >=
                                  interviewRuns.length - 1
                                }
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("analysis_interview_brief", 1);
                                }}
                                type="button"
                              >
                                ▶
                              </button>
                            </div>
                          ) : null}
                          {interviewPreview.previewText ? (
                            <p className="chatContent resultBlockContent">{interviewPreview.previewText}</p>
                          ) : null}
                          {interviewRun ? (
                            <p className="metaText">
                              Fuentes:{" "}
                              {interviewSignalsView.length} ·
                              Pasos agente:{" "}
                              {interviewIterationsView.length} ·
                              Advertencias:{" "}
                              {asStringArray(interviewRun.result_payload["interview_warnings"]).length}
                            </p>
                          ) : null}
                          {interviewReferenceUrls.length > 0 ? (
                            <details
                              className="resultSourcesDetails"
                              onClick={(event) => event.stopPropagation()}
                            >
                              <summary>Fuentes referenciadas ({interviewReferenceUrls.length})</summary>
                              <ul className="resultSourcesList">
                                {interviewReferenceUrls.slice(0, 10).map((url) => (
                                  <li className="resultSourcesItem" key={url}>
                                    <ExternalUrlText url={url} />
                                  </li>
                                ))}
                              </ul>
                            </details>
                          ) : null}
                          {interviewContent &&
                          (interviewPreview.truncated ||
                            expandedResultBlocks.analysis_interview_brief) ? (
                            <div className="cardActions resultBlockToggleRow">
                              <button
                                aria-label={
                                  expandedResultBlocks.analysis_interview_brief
                                    ? "Contraer contenido"
                                    : "Expandir contenido"
                                }
                                className="iconOnlyButton"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleToggleResultBlockPreview("analysis_interview_brief");
                                }}
                                title={
                                  expandedResultBlocks.analysis_interview_brief
                                    ? "Contraer"
                                    : "Expandir"
                                }
                                type="button"
                              >
                                <ExpandCollapseIcon
                                  expanded={expandedResultBlocks.analysis_interview_brief}
                                />
                              </button>
                            </div>
                          ) : null}
                          </article>
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="analysisResultSubTabsWrap">
                          <p className="analysisSubTabHint">Bloques de postulación</p>
                          <div
                            aria-label="Bloques de postulación"
                            className="opportunityModeTabs opportunityModeTabsCompact opportunityModeTabsWrap"
                            role="tablist"
                          >
                            {POSTULATION_MENU_BLOCKS.map((item) => (
                              <button
                                aria-selected={selectedResultBlockId === item.id}
                                className={
                                  selectedResultBlockId === item.id
                                    ? "opportunityModeTab opportunityModeTabActive"
                                    : "opportunityModeTab"
                                }
                                key={item.id}
                                onClick={() => handleSelectResultBlock(item.id)}
                                role="tab"
                                type="button"
                              >
                                {item.label}
                              </button>
                            ))}
                          </div>
                        </div>
                        <div className="resultBlockList">
                        <article
                          className={
                            selectedResultBlockId !== "artifact_guidance_text"
                              ? "resultBlockCard resultBlockCardHidden"
                              : selectedResultBlockId === "artifact_guidance_text"
                              ? "resultBlockCard resultBlockCardActive"
                              : "resultBlockCard"
                          }
                          onClick={() => handleSelectResultBlock("artifact_guidance_text")}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              handleSelectResultBlock("artifact_guidance_text");
                            }
                          }}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="resultBlockTop">
                            <div>
                              <p className="chatRole">{BLOCK_LABEL_BY_ID.artifact_guidance_text}</p>
                              <p className="metaText">
                                {guidanceRun
                                  ? `Generado · ${formatAiRunTimestamp(guidanceRun.updated_at)}`
                                  : "Sin generar"}
                              </p>
                              {guidancePromptBadge ? (
                                <span
                                  className="promptBadge"
                                  title={guidancePromptBadge.tooltip}
                                >
                                  {guidancePromptBadge.label}
                                </span>
                              ) : null}
                            </div>
                            <div className="cardActions">
                              {guidanceRun ? (
                                <button
                                  aria-label="Recalcular guia de perfil"
                                  className="iconOnlyButton"
                                  disabled={isPreparing}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handlePrepare(
                                          selectedOpportunity.opportunity_id,
                                          true,
                                          ["guidance_text"]
                                        )
                                      : undefined;
                                  }}
                                  title="Recalcular"
                                  type="button"
                                >
                                  {isPreparing ? <SpinnerIcon /> : "↻"}
                                </button>
                              ) : (
                                <button
                                  aria-label="Generar guia de perfil"
                                  className="iconOnlyButton"
                                  disabled={isPreparing}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handlePrepare(
                                          selectedOpportunity.opportunity_id,
                                          undefined,
                                          ["guidance_text"]
                                        )
                                      : undefined;
                                  }}
                                  title="Generar"
                                  type="button"
                                >
                                  {isPreparing ? <SpinnerIcon /> : "▶"}
                                </button>
                              )}
                              {guidanceContent ? (
                                <button
                                  aria-label="Copiar guia de perfil"
                                  className="iconOnlyButton"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void handleCopyArtifactContent("guidance_text", guidanceContent);
                                  }}
                                  title={copiedArtifactKey === "guidance_text" ? "Copiado" : "Copiar"}
                                  type="button"
                                >
                                  {copiedArtifactKey === "guidance_text" ? "✓" : "⧉"}
                                </button>
                              ) : null}
                            </div>
                          </div>
                          {guidanceRuns.length > 1 ? (
                            <div className="resultBlockPager">
                              <button
                                className="ghostButton compactActionButton"
                                disabled={getCurrentRunIndexForBlock("artifact_guidance_text") === 0}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("artifact_guidance_text", -1);
                                }}
                                type="button"
                              >
                                ◀
                              </button>
                              <span className="metaText">
                                {getCurrentRunIndexForBlock("artifact_guidance_text") + 1}/
                                {guidanceRuns.length}
                              </span>
                              <button
                                className="ghostButton compactActionButton"
                                disabled={
                                  getCurrentRunIndexForBlock("artifact_guidance_text") >=
                                  guidanceRuns.length - 1
                                }
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("artifact_guidance_text", 1);
                                }}
                                type="button"
                              >
                                ▶
                              </button>
                            </div>
                          ) : null}
                          {guidancePreview.previewText ? (
                            <p className="chatContent resultBlockContent">{guidancePreview.previewText}</p>
                          ) : null}
                          {guidanceContent &&
                          (guidancePreview.truncated ||
                            expandedResultBlocks.artifact_guidance_text) ? (
                            <div className="cardActions resultBlockToggleRow">
                              <button
                                aria-label={
                                  expandedResultBlocks.artifact_guidance_text
                                    ? "Contraer contenido"
                                    : "Expandir contenido"
                                }
                                className="iconOnlyButton"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleToggleResultBlockPreview("artifact_guidance_text");
                                }}
                                title={
                                  expandedResultBlocks.artifact_guidance_text
                                    ? "Contraer"
                                    : "Expandir"
                                }
                                type="button"
                              >
                                <ExpandCollapseIcon
                                  expanded={expandedResultBlocks.artifact_guidance_text}
                                />
                              </button>
                            </div>
                          ) : null}
                        </article>

                        <article
                          className={
                            selectedResultBlockId !== "artifact_cover_letter"
                              ? "resultBlockCard resultBlockCardHidden"
                              : selectedResultBlockId === "artifact_cover_letter"
                              ? "resultBlockCard resultBlockCardActive"
                              : "resultBlockCard"
                          }
                          onClick={() => handleSelectResultBlock("artifact_cover_letter")}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              handleSelectResultBlock("artifact_cover_letter");
                            }
                          }}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="resultBlockTop">
                            <div>
                              <p className="chatRole">{BLOCK_LABEL_BY_ID.artifact_cover_letter}</p>
                              <p className="metaText">
                                {coverRun
                                  ? `Generado · ${formatAiRunTimestamp(coverRun.updated_at)}`
                                  : "Sin generar"}
                              </p>
                              {coverPromptBadge ? (
                                <span
                                  className="promptBadge"
                                  title={coverPromptBadge.tooltip}
                                >
                                  {coverPromptBadge.label}
                                </span>
                              ) : null}
                            </div>
                            <div className="cardActions">
                              {coverRun ? (
                                <button
                                  aria-label="Recalcular carta de presentacion"
                                  className="iconOnlyButton"
                                  disabled={isPreparing}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handlePrepare(
                                          selectedOpportunity.opportunity_id,
                                          true,
                                          ["cover_letter"]
                                        )
                                      : undefined;
                                  }}
                                  title="Recalcular"
                                  type="button"
                                >
                                  {isPreparing ? <SpinnerIcon /> : "↻"}
                                </button>
                              ) : (
                                <button
                                  aria-label="Generar carta de presentacion"
                                  className="iconOnlyButton"
                                  disabled={isPreparing}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handlePrepare(
                                          selectedOpportunity.opportunity_id,
                                          undefined,
                                          ["cover_letter"]
                                        )
                                      : undefined;
                                  }}
                                  title="Generar"
                                  type="button"
                                >
                                  {isPreparing ? <SpinnerIcon /> : "▶"}
                                </button>
                              )}
                              {coverContent ? (
                                <button
                                  aria-label="Copiar carta de presentacion"
                                  className="iconOnlyButton"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void handleCopyArtifactContent("cover_letter", coverContent);
                                  }}
                                  title={copiedArtifactKey === "cover_letter" ? "Copiado" : "Copiar"}
                                  type="button"
                                >
                                  {copiedArtifactKey === "cover_letter" ? "✓" : "⧉"}
                                </button>
                              ) : null}
                            </div>
                          </div>
                          {coverRuns.length > 1 ? (
                            <div className="resultBlockPager">
                              <button
                                className="ghostButton compactActionButton"
                                disabled={getCurrentRunIndexForBlock("artifact_cover_letter") === 0}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("artifact_cover_letter", -1);
                                }}
                                type="button"
                              >
                                ◀
                              </button>
                              <span className="metaText">
                                {getCurrentRunIndexForBlock("artifact_cover_letter") + 1}/
                                {coverRuns.length}
                              </span>
                              <button
                                className="ghostButton compactActionButton"
                                disabled={
                                  getCurrentRunIndexForBlock("artifact_cover_letter") >=
                                  coverRuns.length - 1
                                }
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("artifact_cover_letter", 1);
                                }}
                                type="button"
                              >
                                ▶
                              </button>
                            </div>
                          ) : null}
                          {coverPreview.previewText ? (
                            <p className="chatContent resultBlockContent">{coverPreview.previewText}</p>
                          ) : null}
                          {coverContent &&
                          (coverPreview.truncated || expandedResultBlocks.artifact_cover_letter) ? (
                            <div className="cardActions resultBlockToggleRow">
                              <button
                                aria-label={
                                  expandedResultBlocks.artifact_cover_letter
                                    ? "Contraer contenido"
                                    : "Expandir contenido"
                                }
                                className="iconOnlyButton"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleToggleResultBlockPreview("artifact_cover_letter");
                                }}
                                title={
                                  expandedResultBlocks.artifact_cover_letter
                                    ? "Contraer"
                                    : "Expandir"
                                }
                                type="button"
                              >
                                <ExpandCollapseIcon
                                  expanded={expandedResultBlocks.artifact_cover_letter}
                                />
                              </button>
                            </div>
                          ) : null}
                        </article>

                        <article
                          className={
                            selectedResultBlockId !== "artifact_experience_summary"
                              ? "resultBlockCard resultBlockCardHidden"
                              : selectedResultBlockId === "artifact_experience_summary"
                              ? "resultBlockCard resultBlockCardActive"
                              : "resultBlockCard"
                          }
                          onClick={() => handleSelectResultBlock("artifact_experience_summary")}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              handleSelectResultBlock("artifact_experience_summary");
                            }
                          }}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="resultBlockTop">
                            <div>
                              <p className="chatRole">{BLOCK_LABEL_BY_ID.artifact_experience_summary}</p>
                              <p className="metaText">
                                {summaryRun
                                  ? `Generado · ${formatAiRunTimestamp(summaryRun.updated_at)}`
                                  : "Sin generar"}
                              </p>
                              {summaryPromptBadge ? (
                                <span
                                  className="promptBadge"
                                  title={summaryPromptBadge.tooltip}
                                >
                                  {summaryPromptBadge.label}
                                </span>
                              ) : null}
                            </div>
                            <div className="cardActions">
                              {summaryRun ? (
                                <button
                                  aria-label="Recalcular resumen adaptado"
                                  className="iconOnlyButton"
                                  disabled={isPreparing}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handlePrepare(
                                          selectedOpportunity.opportunity_id,
                                          true,
                                          ["experience_summary"]
                                        )
                                      : undefined;
                                  }}
                                  title="Recalcular"
                                  type="button"
                                >
                                  {isPreparing ? <SpinnerIcon /> : "↻"}
                                </button>
                              ) : (
                                <button
                                  aria-label="Generar resumen adaptado"
                                  className="iconOnlyButton"
                                  disabled={isPreparing}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    selectedOpportunity
                                      ? void handlePrepare(
                                          selectedOpportunity.opportunity_id,
                                          undefined,
                                          ["experience_summary"]
                                        )
                                      : undefined;
                                  }}
                                  title="Generar"
                                  type="button"
                                >
                                  {isPreparing ? <SpinnerIcon /> : "▶"}
                                </button>
                              )}
                              {summaryContent ? (
                                <button
                                  aria-label="Copiar resumen adaptado"
                                  className="iconOnlyButton"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void handleCopyArtifactContent(
                                      "experience_summary",
                                      summaryContent
                                    );
                                  }}
                                  title={copiedArtifactKey === "experience_summary" ? "Copiado" : "Copiar"}
                                  type="button"
                                >
                                  {copiedArtifactKey === "experience_summary" ? "✓" : "⧉"}
                                </button>
                              ) : null}
                            </div>
                          </div>
                          {summaryRuns.length > 1 ? (
                            <div className="resultBlockPager">
                              <button
                                className="ghostButton compactActionButton"
                                disabled={getCurrentRunIndexForBlock("artifact_experience_summary") === 0}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("artifact_experience_summary", -1);
                                }}
                                type="button"
                              >
                                ◀
                              </button>
                              <span className="metaText">
                                {getCurrentRunIndexForBlock("artifact_experience_summary") + 1}/
                                {summaryRuns.length}
                              </span>
                              <button
                                className="ghostButton compactActionButton"
                                disabled={
                                  getCurrentRunIndexForBlock("artifact_experience_summary") >=
                                  summaryRuns.length - 1
                                }
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleMoveRunCursor("artifact_experience_summary", 1);
                                }}
                                type="button"
                              >
                                ▶
                              </button>
                            </div>
                          ) : null}
                          {summaryPreview.previewText ? (
                            <p className="chatContent resultBlockContent">{summaryPreview.previewText}</p>
                          ) : null}
                          {summaryContent &&
                          (summaryPreview.truncated ||
                            expandedResultBlocks.artifact_experience_summary) ? (
                            <div className="cardActions resultBlockToggleRow">
                              <button
                                aria-label={
                                  expandedResultBlocks.artifact_experience_summary
                                    ? "Contraer contenido"
                                    : "Expandir contenido"
                                }
                                className="iconOnlyButton"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleToggleResultBlockPreview("artifact_experience_summary");
                                }}
                                title={
                                  expandedResultBlocks.artifact_experience_summary
                                    ? "Contraer"
                                    : "Expandir"
                                }
                                type="button"
                              >
                                <ExpandCollapseIcon
                                  expanded={expandedResultBlocks.artifact_experience_summary}
                                />
                              </button>
                            </div>
                          ) : null}
                        </article>
                      </div>
                      </>
                    )}
                  </article>

                  <details className="collapsibleSection analysisOpportunityOps">
                    <summary>Gestion de oportunidad</summary>
                    <article className="manualCard analysisActiveCard">
                      <div className="analysisStatusRow">
                        <label className="field analysisStatusField">
                          Estado (V1)
                          <select
                            disabled={isSavingStatus}
                            onChange={(event) => setOpportunityStatus(event.target.value)}
                            value={opportunityStatus}
                          >
                            {OPPORTUNITY_STATUSES.map((status) => (
                              <option key={status} value={status}>
                                {status}
                              </option>
                            ))}
                          </select>
                        </label>
                        <div className="cardActions alignEnd">
                          <button
                            className="primaryButton"
                            disabled={isSavingStatus}
                            onClick={() => void handleSaveStatus()}
                            type="button"
                          >
                            {isSavingStatus ? "Guardando estado..." : "Guardar estado"}
                          </button>
                        </div>
                      </div>
                      {statusSaveMessage ? <p className="successText">{statusSaveMessage}</p> : null}

                      <label className="field">
                        Notas operativas (V1)
                        <textarea
                          disabled={isSavingNotes}
                          onChange={(event) => setOpportunityNotes(event.target.value)}
                          rows={4}
                          value={opportunityNotes}
                        />
                      </label>

                      <div className="analysisNotesRow">
                        <div className="cardActions">
                          <button
                            className="primaryButton"
                            disabled={isSavingNotes}
                            onClick={() => void handleSaveNotes()}
                            type="button"
                          >
                            {isSavingNotes ? "Guardando notas..." : "Guardar notas"}
                          </button>
                        </div>
                      </div>
                    </article>
                  </details>
                </>
              ) : (
                <article className="manualCard analysisEmptyCard">
                  <p className="metaText">
                    Sin oportunidad activa.
                  </p>
                </article>
              )}
            </div>

            {!isContextRailCollapsed ? (
            <aside className="analysisRail analysisRailRight">
              <header className="analysisColumnHeader">
                <h3>Contextual Intelligence</h3>
                <button
                  aria-label="Ocultar contexto de historial y trazas"
                  className="iconOnlyButton contextRailToggleButton hasTooltip"
                  data-tooltip="Ocultar contexto"
                  onClick={() => setIsContextRailCollapsed(true)}
                  title="Ocultar contexto"
                  type="button"
                >
                  <ContextPanelIcon />
                </button>
              </header>

              {!selectedOpportunity ? (
                <article className="manualCard analysisEmptyCard">
                  <p className="metaText">Sin oportunidad activa.</p>
                </article>
              ) : (
                <>
                  <details className="collapsibleSection analysisContextSection" open>
                    <summary>Historial IA</summary>
                    {!focusedRun ? (
                      <p className="metaText">
                        Selecciona un bloque de resultados para ver su ejecucion.
                      </p>
                    ) : (
                      <article className="manualCard">
                        <p className="chatRole">
                          {selectedResultBlockId
                            ? BLOCK_LABEL_BY_ID[selectedResultBlockId]
                            : AI_RUN_ACTION_LABELS[focusedRun.action_key] ?? focusedRun.action_key}
                        </p>
                        <p className="metaText">
                          run_id: {focusedRun.run_id} · actualizado:{" "}
                          {formatAiRunTimestamp(focusedRun.updated_at)}
                        </p>
                        {focusedRun ? (() => {
                          const flowKey = ACTION_TO_FLOW_KEY[focusedRun.action_key];
                          const badge = flowKey
                            ? getPromptBadgeForFlow(
                                focusedRun.result_payload as Record<string, unknown>,
                                flowKey
                              )
                            : null;
                          return badge ? (
                            <span className="promptBadge" title={badge.tooltip}>
                              {badge.label}
                            </span>
                          ) : null;
                        })() : null}
                        <details className="payloadDetails">
                          <summary>Ver response payload persistido</summary>
                          <pre className="payloadPre">
                            {JSON.stringify(focusedRun.result_payload, null, 2)}
                          </pre>
                        </details>
                      </article>
                    )}
                  </details>

                  <details className="collapsibleSection analysisContextSection" open>
                    <summary>Trazas tecnicas</summary>
                    {!focusedRunId ? (
                      <p className="metaText">No hay run activo para mostrar trazas.</p>
                    ) : isLoadingRequestTraces ? (
                      <p className="metaText">Cargando trazas...</p>
                    ) : requestTraces.length === 0 ? (
                      <p className="metaText">
                        No hay trazas disponibles para el run seleccionado.
                      </p>
                    ) : (
                      <div className="chatList">
                        {focusedRunRequestTraces.map((trace) => (
                          <article className="chatBubble chatBubbleAssistant" key={trace.trace_id}>
                            <p className="chatRole">
                              {trace.step_order > 0 ? `Paso ${trace.step_order} · ` : ""}
                              {trace.destination.toUpperCase()} · {trace.flow_key}
                            </p>
                            <p className="metaText">
                              trace_id: {trace.trace_id} · run_id: {trace.run_id || "N/A"} · fecha:{" "}
                              {formatRequestTraceTimestamp(trace.created_at)}
                            </p>
                            {(trace.tool_name || trace.stage || trace.status) && (
                              <p className="metaText">
                                tool: {trace.tool_name || "n/a"} · etapa: {trace.stage || "n/a"} · estado:{" "}
                                {getTraceStatusLabel(trace.status)}
                              </p>
                            )}
                            {trace.input_summary ? (
                              <p className="metaText">input: {trace.input_summary}</p>
                            ) : null}
                            {trace.output_summary ? (
                              <p className="metaText">output: {trace.output_summary}</p>
                            ) : null}
                            {(trace.started_at || trace.finished_at) && (
                              <p className="metaText">
                                inicio: {trace.started_at ? formatRequestTraceTimestamp(trace.started_at) : "n/a"} ·
                                fin: {trace.finished_at ? formatRequestTraceTimestamp(trace.finished_at) : "n/a"}
                              </p>
                            )}
                            <details className="payloadDetails">
                              <summary>Ver request exacto</summary>
                              <pre className="payloadPre">
                                {JSON.stringify(trace.request_payload, null, 2)}
                              </pre>
                            </details>
                            <details className="payloadDetails">
                              <summary>Ver response exacto</summary>
                              <pre className="payloadPre">
                                {JSON.stringify(trace.response_payload ?? {}, null, 2)}
                              </pre>
                            </details>
                          </article>
                        ))}
                      </div>
                    )}
                  </details>
                </>
              )}
            </aside>
            ) : null}
          </div>
              ,
              analysisDetailMountNode
            )
            : null}
        </section>
      ) : null}
      {errorMessage ? <p className="errorText">{errorMessage}</p> : null}
    </main>
  );
}
