import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ComponentType,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  addEdge,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type NodeProps,
} from "@xyflow/react";
import {
  Bell,
  BookmarkPlus,
  CircleStop,
  Database,
  Download,
  FilePlus2,
  Filter,
  FolderOpen,
  GitBranch,
  LockKeyhole,
  Network,
  Play,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Sigma,
  SlidersHorizontal,
  Star,
  Table2,
  Trash2,
} from "lucide-react";
import "@xyflow/react/dist/style.css";

import { findAttribute, starterAttributes } from "./attributeRegistry";
import { DecisionsPanel } from "./features/decisions/DecisionsPanel";
import { InsightCardsPanel } from "./features/insights/InsightCardsPanel";
import { AttributeSourceBadge } from "./features/observations/AttributeSourceBadge";
import { StrategyFitBadge } from "./features/translations/StrategyFitBadge";
import { StrategyExchangeInbox } from "./features/vizaFiles/StrategyExchangeInbox";
import { VizaExportWizard } from "./features/vizaFiles/VizaExportWizard";
import { VizaFileViewer } from "./features/vizaFiles/VizaFileViewer";
import {
  exportVizaFile,
  fetchVizaFileRecords,
  importVizaFile,
  inspectVizaFile,
} from "./features/vizaFiles/fileClient";
import type {
  VizaFileExportRequest,
  VizaFileImportRequest,
  VizaFileRecordResponse,
  VizaFileVisualization,
} from "./features/vizaFiles/types";
import {
  createVizaAlert,
  createVizaValidationRecord,
  cancelRuntimeJob,
  createRuntimeJob,
  createVizaWatchlist,
  executeVizaBatch,
  exportEquityPreviewPackageDraft,
  exportVizaPayload,
  fetchEquityPreviewRunDetail,
  fetchEquityPreviewRuns,
  fetchRuntimeJob,
  fetchRuntimeJobEvents,
  fetchEquityRuntimeWedgeStatus,
  fetchVizaRunRecord,
  fetchVizaAttributes,
  fetchVizaConnectors,
  fetchVizaDiagnostics,
  fetchDefaultVizaProject,
  fetchVizaMethodologyVersion,
  fetchVizaMethodologyVersions,
  fetchVizaVersionDiff,
  fetchVizaUniverses,
  previewEquityRuntimeWedge,
  replayEquityPreviewRun,
  resetVizaEngineRequestConfig,
  saveVizaRadarSchedule,
  saveVizaRadarOutput,
  saveVizaMethodologyVersion,
} from "./vizaEngineClient";
import type { VizaDesktopStatus } from "./electron";
import {
  isVizaEdgeType,
  isVizaNodeType,
  VIZA_GRAPH_SCHEMA_VERSION,
  type VizaEdgeType,
  type MethodologyRunResult,
  type VizaAttributeDefinition,
  type VizaBatchExecutionResult,
  type VizaBatchExecutionRequest,
  type VizaAlertDefinition,
  type VizaExportFormat,
  type VizaEquityRuntimeWedgePreview,
  type VizaEquityRuntimeWedgeStatus,
  type VizaEquityPreviewRunDetail,
  type VizaEquityPreviewRunSummary,
  type VizaEquityPreviewPackageDraftResponse,
  type VizaConnectorDefinition,
  type VizaGraphEdge,
  type VizaGraphNode,
  type VizaMethodologyVersionDiff,
  type VizaMethodologyVersionSummary,
  type VizaMethodologyGraph,
  type VizaNodeType,
  type VizaProjectSummary,
  type VizaRadarRow,
  type VizaRelationshipEdge,
  type VizaRuntimeDiagnostics,
  type VizaRuntimeJobEvent,
  type VizaRuntimeJobRecord,
  type VizaValidationRecord,
  type VizaUniverseSummary,
} from "./vizaGraph";

interface VizaCanvasNodeData extends Record<string, unknown> {
  vizaType: VizaNodeType;
  label: string;
  config: Record<string, unknown>;
}

interface VizaCanvasEdgeData extends Record<string, unknown> {
  vizaEdgeType: VizaEdgeType;
  config: Record<string, unknown>;
}

type VizaFlowNode = Node<VizaCanvasNodeData, "vizaNode">;
type VizaFlowEdge = Edge<VizaCanvasEdgeData>;
type IconComponent = ComponentType<{ size?: number; strokeWidth?: number }>;
type EngineStatus = "checking" | "online" | "offline";
type MetadataSource = "engine" | "fallback";
type NodeReadiness = "ready" | "not_configured";
type RelationshipGraphNodeKind =
  | "entity"
  | "asset"
  | "attribute"
  | "sector"
  | "industry"
  | "peer"
  | "event"
  | "insight"
  | "strategy_profile"
  | "output";
type RadarSortDirection = "ascending" | "descending";

interface RadarInsightFilters {
  insightType: string;
  minConfidence: string;
  minStrategyFitScore: string;
  missingConfirmation: string;
  pitStatus: string;
  riskFlag: string;
  sourceRestriction: string;
}

interface RelationshipGraphNode {
  id: string;
  label: string;
  kind: RelationshipGraphNodeKind;
  x: number;
  y: number;
  evidenceRef: string | null;
}

interface NodeDefinition {
  label: string;
  accent: string;
  icon: IconComponent;
  moduleId: string;
  moduleType: string;
  defaultConfig: () => Record<string, unknown>;
}

const NODE_DEFINITIONS: Record<VizaNodeType, NodeDefinition> = {
  universe: {
    label: "Universe",
    accent: "#0f766e",
    icon: Database,
    moduleId: "viza.finance.securities",
    moduleType: "viza.finance.securities.universe",
    defaultConfig: () => ({
      universe_name: "pilot_sp500_static",
      universe_version: "sp500_static_2026_05_06_v0",
      ticker_subset: [],
    }),
  },
  attribute: {
    label: "Attribute",
    accent: "#2563eb",
    icon: SlidersHorizontal,
    moduleId: "viza.finance.securities",
    moduleType: "viza.finance.securities.attribute",
    defaultConfig: () => ({
      attribute_key: "unexplained_residual_bps",
      lookback_days: 1,
      missing_data: "warn_and_exclude_from_score",
    }),
  },
  transform: {
    label: "Transform",
    accent: "#7c3aed",
    icon: GitBranch,
    moduleId: "viza.finance.securities",
    moduleType: "viza.finance.securities.transform",
    defaultConfig: () => ({
      transform: "percentile_rank",
      direction: "higher_is_better",
    }),
  },
  filter: {
    label: "Filter",
    accent: "#b45309",
    icon: Filter,
    moduleId: "viza.finance.securities",
    moduleType: "viza.finance.securities.filter",
    defaultConfig: () => ({
      operator: "is_available",
      attribute_key: "unexplained_residual_bps",
    }),
  },
  score: {
    label: "Score",
    accent: "#c026d3",
    icon: Sigma,
    moduleId: "viza.finance.securities",
    moduleType: "viza.finance.securities.score",
    defaultConfig: () => ({
      method: "weighted_sum",
      weights: {},
      missing_data: "renormalize_available_weights",
    }),
  },
  relationship: {
    label: "Relationship",
    accent: "#0891b2",
    icon: Network,
    moduleId: "viza.finance.securities",
    moduleType: "viza.finance.securities.relationship",
    defaultConfig: () => ({
      relationships: ["company_to_selected_attributes", "company_to_sector"],
    }),
  },
  output_radar: {
    label: "Output Radar",
    accent: "#16a34a",
    icon: Table2,
    moduleId: "viza.finance.securities",
    moduleType: "viza.finance.securities.output_radar",
    defaultConfig: () => ({
      top_n: 25,
      sort: "descending",
      columns: ["ticker", "company_name", "score", "unexplained_residual_bps"],
    }),
  },
};

const TOOLBAR_NODE_TYPES: VizaNodeType[] = [
  "universe",
  "attribute",
  "transform",
  "filter",
  "score",
  "output_radar",
  "relationship",
];

const nodeTypes = {
  vizaNode: VizaNode,
};

export default function App() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const createdAtRef = useRef(new Date().toISOString());
  const [methodologyId, setMethodologyId] = useState(() => `methodology-${shortId()}`);
  const [graphName, setGraphName] = useState("Untitled Methodology");
  const [status, setStatus] = useState("Blank canvas ready.");
  const [engineStatus, setEngineStatus] = useState<EngineStatus>("checking");
  const [metadataSource, setMetadataSource] = useState<MetadataSource>("fallback");
  const [engineMetadataError, setEngineMetadataError] = useState<string | null>(null);
  const [engineAttributes, setEngineAttributes] =
    useState<VizaAttributeDefinition[]>(starterAttributes);
  const [engineUniverses, setEngineUniverses] = useState<VizaUniverseSummary[]>([]);
  const [engineConnectors, setEngineConnectors] = useState<VizaConnectorDefinition[]>([]);
  const [runtimeDiagnostics, setRuntimeDiagnostics] = useState<VizaRuntimeDiagnostics | null>(null);
  const [desktopStatus, setDesktopStatus] = useState<VizaDesktopStatus | null>(null);
  const [activeProject, setActiveProject] = useState<VizaProjectSummary | null>(null);
  const [methodologyVersions, setMethodologyVersions] = useState<
    VizaMethodologyVersionSummary[]
  >([]);
  const [versionDiff, setVersionDiff] = useState<VizaMethodologyVersionDiff | null>(null);
  const [runResult, setRunResult] = useState<MethodologyRunResult | null>(null);
  const [batchResult, setBatchResult] = useState<VizaBatchExecutionResult | null>(null);
  const [runtimeJob, setRuntimeJob] = useState<VizaRuntimeJobRecord | null>(null);
  const [runtimeJobEvents, setRuntimeJobEvents] = useState<VizaRuntimeJobEvent[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isBatchRunning, setIsBatchRunning] = useState(false);
  const [isRestartingEngine, setIsRestartingEngine] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<VizaFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<VizaFlowEdge>([]);

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );

  const loadVersionHistory = useCallback(
    async (targetMethodologyId: string, projectId: string) => {
      const versions = await fetchVizaMethodologyVersions(targetMethodologyId, projectId);
      setMethodologyVersions(versions);
      const latestVersion = versions[0];
      const previousVersion = versions[1];
      if (latestVersion && previousVersion) {
        const diff = await fetchVizaVersionDiff(
          targetMethodologyId,
          previousVersion.version_id,
          latestVersion.version_id,
        );
        setVersionDiff(diff);
      } else {
        setVersionDiff(null);
      }
      return versions;
    },
    [],
  );

  const refreshEngineMetadata = useCallback(async () => {
    setEngineStatus("checking");
    try {
      const desktopStatusPromise = window.vizaDesktop
        ? window.vizaDesktop.desktopStatus()
        : Promise.resolve(null);
      const [
        attributeRegistryResult,
        universesResult,
        connectorsResult,
        projectResult,
        diagnosticsResult,
        statusSnapshotResult,
      ] = await Promise.allSettled([
          fetchVizaAttributes(),
          fetchVizaUniverses(),
          fetchVizaConnectors(),
          fetchDefaultVizaProject(),
          fetchVizaDiagnostics(),
          desktopStatusPromise,
        ]);

      const metadataErrors: string[] = [];
      if (statusSnapshotResult.status === "fulfilled") {
        setDesktopStatus(statusSnapshotResult.value);
      }
      if (attributeRegistryResult.status === "fulfilled") {
        setEngineAttributes(attributeRegistryResult.value.attributes);
        setMetadataSource("engine");
      } else {
        setEngineAttributes(starterAttributes);
        setMetadataSource("fallback");
        metadataErrors.push(`attributes: ${errorMessage(attributeRegistryResult.reason)}`);
      }
      if (universesResult.status === "fulfilled") {
        setEngineUniverses(universesResult.value);
      } else {
        setEngineUniverses([]);
        metadataErrors.push(`universes: ${errorMessage(universesResult.reason)}`);
      }
      if (connectorsResult.status === "fulfilled") {
        setEngineConnectors(connectorsResult.value);
      } else {
        setEngineConnectors([]);
        metadataErrors.push(`connectors: ${errorMessage(connectorsResult.reason)}`);
      }
      if (projectResult.status === "fulfilled") {
        setActiveProject(projectResult.value);
        try {
          await loadVersionHistory(methodologyId, projectResult.value.project_id);
        } catch (error) {
          metadataErrors.push(`versions: ${errorMessage(error)}`);
        }
      } else {
        setActiveProject(null);
        metadataErrors.push(`project: ${errorMessage(projectResult.reason)}`);
      }
      if (diagnosticsResult.status === "fulfilled") {
        setRuntimeDiagnostics(diagnosticsResult.value);
      } else {
        setRuntimeDiagnostics(null);
        metadataErrors.push(`diagnostics: ${errorMessage(diagnosticsResult.reason)}`);
      }

      const engineResponded = [
        attributeRegistryResult,
        universesResult,
        connectorsResult,
        projectResult,
        diagnosticsResult,
      ].some((result) => result.status === "fulfilled");
      if (!engineResponded) {
        throw new Error(metadataErrors[0] || "VIZA engine is offline.");
      }

      setEngineStatus("online");
      setEngineMetadataError(metadataErrors.length ? metadataErrors.join(" | ") : null);
      if (metadataErrors.length) {
        setStatus(`Engine online, but metadata is incomplete. ${metadataErrors[0]}`);
      } else {
        const attributeCount =
          attributeRegistryResult.status === "fulfilled"
            ? attributeRegistryResult.value.attributes.length
            : starterAttributes.length;
        const universeCount =
          universesResult.status === "fulfilled" ? universesResult.value.length : 0;
        const connectorCount =
          connectorsResult.status === "fulfilled" ? connectorsResult.value.length : 0;
        setStatus(
          `Engine online. ${attributeCount} attributes, ${universeCount} universes, ${connectorCount} connectors.`,
        );
      }
    } catch (error) {
      setEngineStatus("offline");
      setRuntimeDiagnostics(null);
      setMetadataSource("fallback");
      setEngineMetadataError(errorMessage(error));
      setStatus(error instanceof Error ? error.message : "VIZA engine is offline.");
      if (window.vizaDesktop) {
        try {
          setDesktopStatus(await window.vizaDesktop.desktopStatus());
        } catch {
          setDesktopStatus(null);
        }
      }
    }
  }, [loadVersionHistory, methodologyId]);

  useEffect(() => {
    void refreshEngineMetadata();
  }, [refreshEngineMetadata]);

  const restartEngine = useCallback(async () => {
    setIsRestartingEngine(true);
    setEngineStatus("checking");
    setStatus("Restarting VIZA engine.");
    try {
      if (window.vizaDesktop?.restartEngine) {
        const statusSnapshot = await window.vizaDesktop.restartEngine();
        setDesktopStatus(statusSnapshot);
        resetVizaEngineRequestConfig();
      }
      await refreshEngineMetadata();
      setStatus("VIZA engine restarted.");
    } catch (error) {
      setEngineStatus("offline");
      setStatus(error instanceof Error ? error.message : "VIZA engine restart failed.");
      if (window.vizaDesktop) {
        try {
          setDesktopStatus(await window.vizaDesktop.desktopStatus());
        } catch {
          setDesktopStatus(null);
        }
      }
    } finally {
      setIsRestartingEngine(false);
    }
  }, [refreshEngineMetadata]);

  const addCanvasNode = useCallback(
    (vizaType: VizaNodeType) => {
      const definition = NODE_DEFINITIONS[vizaType];
      const id = `${vizaType}-${shortId()}`;
      const index = nodes.length;
      const node: VizaFlowNode = {
        id,
        type: "vizaNode",
        position: {
          x: 140 + (index % 4) * 240,
          y: 120 + Math.floor(index / 4) * 150,
        },
        data: {
          vizaType,
          label: definition.label,
          moduleId: definition.moduleId,
          moduleType: definition.moduleType,
          config: definition.defaultConfig(),
        },
      };

      setNodes((currentNodes) => [...currentNodes, node]);
      setSelectedNodeId(id);
      setRunResult(null);
      setBatchResult(null);
      setIsDirty(true);
      setStatus(`${definition.label} node added.`);
    },
    [nodes.length, setNodes],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const compatibilityMessage = validateCanvasConnection(connection, nodes, edges);
      if (compatibilityMessage) {
        setStatus(compatibilityMessage);
        return;
      }

      const vizaEdgeType = inferEdgeType(connection, nodes);
      const edge: VizaFlowEdge = {
        ...connection,
        id: `edge-${connection.source ?? "source"}-${connection.target ?? "target"}-${shortId()}`,
        type: "smoothstep",
        markerEnd: { type: MarkerType.ArrowClosed },
        data: {
          vizaEdgeType,
          config: {},
        },
        style: edgeStyle(vizaEdgeType),
      };

      setEdges((currentEdges) => addEdge(edge, currentEdges) as VizaFlowEdge[]);
      setStatus("Edge connected.");
      setRunResult(null);
      setBatchResult(null);
      setIsDirty(true);
    },
    [edges, nodes, setEdges],
  );

  const updateNodeData = useCallback(
    (nodeId: string, updater: (data: VizaCanvasNodeData) => VizaCanvasNodeData) => {
      setNodes((currentNodes) =>
        currentNodes.map((node) =>
          node.id === nodeId ? { ...node, data: updater(node.data) } : node,
        ),
      );
      setRunResult(null);
      setBatchResult(null);
      setIsDirty(true);
    },
    [setNodes],
  );

  const deleteNode = useCallback(
    (nodeId: string) => {
      setNodes((currentNodes) => currentNodes.filter((node) => node.id !== nodeId));
      setEdges((currentEdges) =>
        currentEdges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
      );
      setSelectedNodeId(null);
      setRunResult(null);
      setBatchResult(null);
      setIsDirty(true);
      setStatus("Node removed.");
    },
    [setEdges, setNodes],
  );

  const duplicateNode = useCallback(
    (nodeId: string) => {
      const sourceNode = nodes.find((node) => node.id === nodeId);
      if (!sourceNode) {
        return;
      }

      const definition = NODE_DEFINITIONS[sourceNode.data.vizaType];
      const duplicatedNode: VizaFlowNode = {
        ...sourceNode,
        id: `${sourceNode.data.vizaType}-${shortId()}`,
        selected: false,
        position: {
          x: sourceNode.position.x + 36,
          y: sourceNode.position.y + 36,
        },
        data: {
          ...sourceNode.data,
          label: `${sourceNode.data.label} Copy`,
          config: { ...sourceNode.data.config },
        },
      };

      setNodes((currentNodes) => [...currentNodes, duplicatedNode]);
      setSelectedNodeId(duplicatedNode.id);
      setRunResult(null);
      setBatchResult(null);
      setIsDirty(true);
      setStatus(`${definition.label} node duplicated.`);
    },
    [nodes, setNodes],
  );

  const handleNodesChange = useCallback(
    (changes: NodeChange<VizaFlowNode>[]) => {
      onNodesChange(changes);
      if (changes.some((change) => change.type !== "select")) {
        setRunResult(null);
        setBatchResult(null);
        setIsDirty(true);
      }
    },
    [onNodesChange],
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange<VizaFlowEdge>[]) => {
      onEdgesChange(changes);
      if (changes.some((change) => change.type !== "select")) {
        setRunResult(null);
        setBatchResult(null);
        setIsDirty(true);
      }
    },
    [onEdgesChange],
  );

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!selectedNodeId || isEditableTarget(event.target)) {
        return;
      }
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        deleteNode(selectedNodeId);
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "d") {
        event.preventDefault();
        duplicateNode(selectedNodeId);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [deleteNode, duplicateNode, selectedNodeId]);

  const buildGraph = useCallback((): VizaMethodologyGraph => {
    return {
      schema_version: VIZA_GRAPH_SCHEMA_VERSION,
      methodology_id: methodologyId,
      name: graphName.trim() || "Untitled Methodology",
      description: "VIZA Phase 1 canvas methodology.",
      created_at: createdAtRef.current,
      updated_at: new Date().toISOString(),
      nodes: nodes.map(flowNodeToGraphNode),
      edges: edges.map(flowEdgeToGraphEdge),
      metadata: {
        created_with: "viza_desktop_phase_2",
      },
    };
  }, [edges, graphName, methodologyId, nodes]);

  const applyGraph = useCallback(
    (graph: VizaMethodologyGraph) => {
      createdAtRef.current = graph.created_at;
      setMethodologyId(graph.methodology_id);
      setGraphName(graph.name);
      setNodes(graph.nodes.map(graphNodeToFlowNode));
      setEdges(graph.edges.map(graphEdgeToFlowEdge));
      setSelectedNodeId(null);
      setRunResult(null);
      setBatchResult(null);
      setRuntimeJob(null);
      setRuntimeJobEvents([]);
      setIsDirty(false);
      setStatus(`Loaded ${graph.name}.`);
    },
    [setEdges, setNodes],
  );

  const newGraph = useCallback(() => {
    createdAtRef.current = new Date().toISOString();
    setMethodologyId(`methodology-${shortId()}`);
    setGraphName("Untitled Methodology");
    setNodes([]);
    setEdges([]);
    setSelectedNodeId(null);
    setRunResult(null);
    setBatchResult(null);
    setRuntimeJob(null);
    setRuntimeJobEvents([]);
    setIsDirty(false);
    setStatus("New blank canvas ready.");
  }, [setEdges, setNodes]);

  const pollRuntimeJob = useCallback(async (jobId: string) => {
    for (let attempt = 0; attempt < 160; attempt += 1) {
      const [job, events] = await Promise.all([
        fetchRuntimeJob(jobId),
        fetchRuntimeJobEvents(jobId),
      ]);
      setRuntimeJob(job);
      setRuntimeJobEvents(events);
      if (isTerminalJobStatus(job.status)) {
        if (job.status === "completed" && job.result_ref) {
          const record = await fetchVizaRunRecord(job.result_ref);
          if (record.result) {
            setRunResult(record.result);
            setStatus(
              `Run ${record.result.status}. ${record.result.rows.length} rows, ${record.result.warnings.length} warnings.`,
            );
          } else {
            setStatus(`Job completed with result ${job.result_ref}.`);
          }
        } else {
          setStatus(job.progress.message || `Job ${job.status}.`);
        }
        setIsRunning(false);
        setEngineStatus("online");
        return;
      }
      setStatus(job.progress.message || `Job ${job.status}.`);
      await wait(750);
    }
    setStatus("Job is still running; progress will update on the next refresh.");
    setIsRunning(false);
  }, []);

  const runGraph = useCallback(async () => {
    setIsRunning(true);
    setStatus("Starting runtime job.");
    setRuntimeJob(null);
    setRuntimeJobEvents([]);
    try {
      const graph = buildGraph();
      const job = await createRuntimeJob({
        job_type: "methodology_run",
        graph,
        project_id: activeProject?.project_id ?? null,
        methodology_version_id: methodologyVersions[0]?.version_id ?? null,
        start_immediately: true,
        use_cache: true,
      });
      setRuntimeJob(job);
      setEngineStatus("online");
      setStatus(`Started job ${shortVersionId(job.job_id)}.`);
      void pollRuntimeJob(job.job_id);
    } catch (error) {
      setEngineStatus("offline");
      setRunResult(null);
      setStatus(error instanceof Error ? error.message : "VIZA engine execution failed.");
      setIsRunning(false);
    }
  }, [activeProject, buildGraph, methodologyVersions, pollRuntimeJob]);

  const cancelActiveRuntimeJob = useCallback(async () => {
    if (!runtimeJob || isTerminalJobStatus(runtimeJob.status)) {
      return;
    }
    try {
      const job = await cancelRuntimeJob(runtimeJob.job_id);
      setRuntimeJob(job);
      setStatus(job.progress.message || "Cancellation requested.");
      if (isTerminalJobStatus(job.status)) {
        setIsRunning(false);
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not cancel runtime job.");
    }
  }, [runtimeJob]);

  const runBatch = useCallback(
    async (cutoffs: string[], tickerSubset: string[]) => {
      if (!cutoffs.length) {
        setStatus("Add at least one cutoff before running a batch.");
        return;
      }
      setIsBatchRunning(true);
      setStatus(`Running batch across ${cutoffs.length} cutoffs.`);
      try {
        const graph = buildGraph();
        const latestVersionId = methodologyVersions[0]?.version_id ?? null;
        const request: VizaBatchExecutionRequest = {
          cutoffs,
          persist_results: Boolean(activeProject),
          ticker_subset: tickerSubset,
        };
        if (activeProject) {
          request.project_id = activeProject.project_id;
        }
        if (latestVersionId) {
          request.methodologies = [
            {
              graph,
              methodology_version_id: latestVersionId,
              label: graph.name,
            },
          ];
        } else {
          request.graph = graph;
        }

        const result = await executeVizaBatch(request);
        const selectedRun = latestBatchRunResult(result);
        setBatchResult(result);
        if (selectedRun) {
          setRunResult(selectedRun);
        }
        setEngineStatus("online");
        setStatus(
          `Batch ${result.status}. ${result.completed_runs} completed, ${result.failed_runs} failed.`,
        );
      } catch (error) {
        setEngineStatus("offline");
        setStatus(error instanceof Error ? error.message : "VIZA batch execution failed.");
      } finally {
        setIsBatchRunning(false);
      }
    },
    [activeProject, buildGraph, methodologyVersions],
  );

  const saveGraph = useCallback(async () => {
    const graph = buildGraph();

    if (window.vizaDesktop) {
      const result = await window.vizaDesktop.saveGraph(graph);
      if (!result.canceled) {
        setIsDirty(false);
        setStatus(`Saved ${result.path ?? graph.name}.`);
      }
      return;
    }

    downloadGraph(graph);
    setIsDirty(false);
    setStatus("Graph JSON downloaded.");
  }, [buildGraph]);

  const ensureActiveProject = useCallback(async () => {
    if (activeProject) {
      return activeProject;
    }
    const project = await fetchDefaultVizaProject();
    setActiveProject(project);
    return project;
  }, [activeProject]);

  const saveProjectVersion = useCallback(async () => {
    setStatus("Saving methodology version.");
    try {
      const project = await ensureActiveProject();
      const graph = buildGraph();
      const savedVersion = await saveVizaMethodologyVersion({
        graph,
        label: graph.name,
        message: "Saved from VIZA desktop.",
        parentVersionId: methodologyVersions[0]?.version_id ?? null,
        projectId: project.project_id,
      });
      await loadVersionHistory(graph.methodology_id, project.project_id);
      setIsDirty(false);
      setEngineStatus("online");
      setStatus(`Saved version ${shortVersionId(savedVersion.version_id)}.`);
    } catch (error) {
      setEngineStatus("offline");
      setStatus(error instanceof Error ? error.message : "Could not save methodology version.");
    }
  }, [buildGraph, ensureActiveProject, loadVersionHistory, methodologyVersions]);

  const loadProjectVersion = useCallback(
    async (version: VizaMethodologyVersionSummary) => {
      setStatus("Loading methodology version.");
      try {
        const record = await fetchVizaMethodologyVersion(
          version.methodology_id,
          version.version_id,
        );
        applyGraph(record.graph);
        if (activeProject) {
          await loadVersionHistory(record.graph.methodology_id, activeProject.project_id);
        }
        setEngineStatus("online");
        setStatus(`Loaded version ${shortVersionId(version.version_id)}.`);
      } catch (error) {
        setEngineStatus("offline");
        setStatus(error instanceof Error ? error.message : "Could not load methodology version.");
      }
    },
    [activeProject, applyGraph, loadVersionHistory],
  );

  const cloneProjectVersion = useCallback(
    async (version: VizaMethodologyVersionSummary) => {
      setStatus("Cloning methodology version.");
      try {
        const record = await fetchVizaMethodologyVersion(
          version.methodology_id,
          version.version_id,
        );
        const clonedGraph = cloneMethodologyGraph(record.graph);
        applyGraph(clonedGraph);
        setMethodologyVersions([]);
        setVersionDiff(null);
        setIsDirty(true);
        setEngineStatus("online");
        setStatus(`Cloned ${record.name}. Save a version when ready.`);
      } catch (error) {
        setEngineStatus("offline");
        setStatus(error instanceof Error ? error.message : "Could not clone methodology version.");
      }
    },
    [applyGraph],
  );

  const revertToProjectVersion = useCallback(
    async (version: VizaMethodologyVersionSummary) => {
      setStatus("Reverting methodology to selected version.");
      try {
        const project = await ensureActiveProject();
        const record = await fetchVizaMethodologyVersion(
          version.methodology_id,
          version.version_id,
        );
        const revertedGraph = touchMethodologyGraph(record.graph, {
          reverted_from_version_id: version.version_id,
        });
        const savedVersion = await saveVizaMethodologyVersion({
          graph: revertedGraph,
          label: `Revert ${shortVersionId(version.version_id)}`,
          message: `Created by reverting to ${version.version_id}.`,
          parentVersionId: methodologyVersions[0]?.version_id ?? null,
          projectId: project.project_id,
        });
        applyGraph(savedVersion.graph);
        await loadVersionHistory(savedVersion.methodology_id, project.project_id);
        setIsDirty(false);
        setEngineStatus("online");
        setStatus(`Created revert version ${shortVersionId(savedVersion.version_id)}.`);
      } catch (error) {
        setEngineStatus("offline");
        setStatus(error instanceof Error ? error.message : "Could not revert methodology version.");
      }
    },
    [applyGraph, ensureActiveProject, loadVersionHistory, methodologyVersions],
  );

  const openGraph = useCallback(async () => {
    if (window.vizaDesktop) {
      const result = await window.vizaDesktop.openGraph();
      if (!result.canceled && result.graph) {
        applyGraph(parseMethodologyGraph(result.graph));
      }
      return;
    }

    fileInputRef.current?.click();
  }, [applyGraph]);

  const onBrowserFileSelected = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const input = event.currentTarget;
      const file = input.files?.[0];
      if (!file) {
        return;
      }

      try {
        const text = await file.text();
        applyGraph(parseMethodologyGraph(JSON.parse(text)));
      } catch (error) {
        setStatus(error instanceof Error ? error.message : "Could not load graph JSON.");
      } finally {
        input.value = "";
      }
    },
    [applyGraph],
  );

  return (
    <main className="app-shell">
      <aside className="tool-rail" aria-label="VIZA tools">
        <div className="tool-mark">VIZA</div>
        <button className="icon-button" type="button" title="New graph" onClick={newGraph}>
          <FilePlus2 size={18} />
        </button>
        <button className="icon-button" type="button" title="Open graph" onClick={openGraph}>
          <FolderOpen size={18} />
        </button>
        <button className="icon-button" type="button" title="Save graph" onClick={saveGraph}>
          <Save size={18} />
        </button>
        <div className="tool-divider" />
        {TOOLBAR_NODE_TYPES.map((nodeType) => {
          const definition = NODE_DEFINITIONS[nodeType];
          const Icon = definition.icon;
          return (
            <button
              className="tool-button"
              key={nodeType}
              style={{ "--tool-accent": definition.accent } as CSSProperties}
              title={`Add ${definition.label}`}
              type="button"
              onClick={() => addCanvasNode(nodeType)}
            >
              <Icon size={18} />
              <span>{definition.label}</span>
            </button>
          );
        })}
      </aside>

      <section className="workspace">
        <header className="top-bar">
          <input
            aria-label="Methodology name"
            className="methodology-name"
            value={graphName}
            onChange={(event) => {
              setGraphName(event.target.value);
              setIsDirty(true);
            }}
          />
          <div className="status-line">
            <span className={`dirty-pill ${isDirty ? "dirty" : "clean"}`}>
              {isDirty ? "unsaved" : "saved"}
            </span>
            <span>{status}</span>
          </div>
          <div className="top-actions">
            <button
              className="run-button"
              disabled={isRunning}
              type="button"
              title="Run methodology"
              onClick={runGraph}
            >
              <Play size={16} />
              <span>{isRunning ? "Running" : "Run"}</span>
            </button>
            <button
              className="icon-button compact"
              disabled={!runtimeJob || !isRunning || isTerminalJobStatus(runtimeJob.status)}
              type="button"
              title="Cancel runtime job"
              onClick={cancelActiveRuntimeJob}
            >
              <CircleStop size={16} />
            </button>
            <button
              className="version-button"
              type="button"
              title="Save methodology version"
              onClick={saveProjectVersion}
            >
              <Save size={16} />
              <span>Version</span>
            </button>
            <button
              className="icon-button compact"
              type="button"
              title="Refresh engine metadata"
              onClick={refreshEngineMetadata}
            >
              <RefreshCw size={16} />
            </button>
            <span className={`engine-pill ${engineStatus}`}>{engineStatus}</span>
          </div>
        </header>

        <section className="canvas-region">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.25}
            maxZoom={1.6}
            onConnect={onConnect}
            onEdgesChange={handleEdgesChange}
            onNodesChange={handleNodesChange}
            onNodeClick={(_event, node) => setSelectedNodeId(node.id)}
            onPaneClick={() => setSelectedNodeId(null)}
          >
            <Background color="#d6dce5" gap={22} size={1.4} variant={BackgroundVariant.Dots} />
            <Controls position="bottom-left" />
            <MiniMap
              pannable
              zoomable
              nodeBorderRadius={4}
              nodeColor={(node) => {
                const vizaType = readString((node.data as Record<string, unknown>).vizaType);
                return isVizaNodeType(vizaType) ? NODE_DEFINITIONS[vizaType].accent : "#64748b";
              }}
            />
          </ReactFlow>
        </section>
        <ResultPanel
          attributeCount={engineAttributes.length}
          connectors={engineConnectors}
          desktopStatus={desktopStatus}
          diagnostics={runtimeDiagnostics}
          engineStatus={engineStatus}
          metadataError={engineMetadataError}
          metadataSource={metadataSource}
          batchResult={batchResult}
          runtimeJob={runtimeJob}
          runtimeJobEvents={runtimeJobEvents}
          isBatchRunning={isBatchRunning}
          isRestartingEngine={isRestartingEngine}
          isRunning={isRunning}
          project={activeProject}
          result={runResult}
          versionDiff={versionDiff}
          versions={methodologyVersions}
          buildMethodologyGraph={buildGraph}
          universeCount={engineUniverses.length}
          onApplyGraph={applyGraph}
          onCloneVersion={cloneProjectVersion}
          onLoadVersion={loadProjectVersion}
          onRevertVersion={revertToProjectVersion}
          onRestartEngine={restartEngine}
          onRunBatch={runBatch}
          onCancelRuntimeJob={cancelActiveRuntimeJob}
          onSelectBatchRun={setRunResult}
          onRefreshDiagnostics={refreshEngineMetadata}
          onSaveVersion={saveProjectVersion}
        />
      </section>

      <Inspector
        attributeOptions={engineAttributes}
        node={selectedNode}
        nodes={nodes}
        onDelete={deleteNode}
        onDuplicate={duplicateNode}
        onUpdate={updateNodeData}
        universes={engineUniverses}
      />

      <input
        ref={fileInputRef}
        accept="application/json,.json,.viza.json"
        className="hidden-file-input"
        type="file"
        onChange={onBrowserFileSelected}
      />
    </main>
  );
}

function VizaNode({ data, selected }: NodeProps<VizaFlowNode>) {
  const definition = NODE_DEFINITIONS[data.vizaType];
  const Icon = definition.icon;
  const readiness = nodeReadiness(data);

  return (
    <div
      className={`canvas-node ${selected ? "selected" : ""} ${readiness}`}
      style={{ "--node-accent": definition.accent } as CSSProperties}
    >
      <Handle className="node-handle" position={Position.Left} type="target" />
      <div className="canvas-node-header">
        <span className="canvas-node-icon">
          <Icon size={16} />
        </span>
        <span className="canvas-node-label">{data.label}</span>
      </div>
      <div className="canvas-node-subtitle">{nodeSubtitle(data)}</div>
      <div className={`node-status-badge ${readiness}`}>
        {readiness === "ready" ? "ready" : "configure"}
      </div>
      <Handle className="node-handle" position={Position.Right} type="source" />
    </div>
  );
}

function Inspector({
  attributeOptions,
  node,
  nodes,
  onDelete,
  onDuplicate,
  onUpdate,
  universes,
}: {
  attributeOptions: VizaAttributeDefinition[];
  node: VizaFlowNode | null;
  nodes: VizaFlowNode[];
  onDelete: (nodeId: string) => void;
  onDuplicate: (nodeId: string) => void;
  onUpdate: (nodeId: string, updater: (data: VizaCanvasNodeData) => VizaCanvasNodeData) => void;
  universes: VizaUniverseSummary[];
}) {
  if (!node) {
    return (
      <aside className="inspector">
        <div className="inspector-empty">
          <Network size={22} />
          <span>No node selected</span>
        </div>
      </aside>
    );
  }

  const definition = NODE_DEFINITIONS[node.data.vizaType];
  const config = node.data.config;

  const patchConfig = (patch: Record<string, unknown>) => {
    onUpdate(node.id, (data) => ({
      ...data,
      config: {
        ...data.config,
        ...patch,
      },
    }));
  };

  const patchNode = (patch: Partial<Pick<VizaCanvasNodeData, "label" | "config">>) => {
    onUpdate(node.id, (data) => ({
      ...data,
      ...patch,
      config: patch.config ?? data.config,
    }));
  };

  return (
    <aside className="inspector">
      <div className="inspector-header">
        <div>
          <span className="node-type-pill" style={{ color: definition.accent }}>
            {definition.label}
          </span>
          <h2>{node.data.label}</h2>
        </div>
        <div className="inspector-actions">
          <button
            className="icon-button"
            type="button"
            title="Duplicate node"
            onClick={() => onDuplicate(node.id)}
          >
            <FilePlus2 size={18} />
          </button>
          <button
            className="icon-button danger"
            type="button"
            title="Delete node"
            onClick={() => onDelete(node.id)}
          >
            <Trash2 size={18} />
          </button>
        </div>
      </div>

      <Field label="Label">
        <input
          value={node.data.label}
          onChange={(event) => patchNode({ label: event.target.value })}
        />
      </Field>

      {node.data.vizaType === "universe" && (
        <UniverseFields config={config} onPatch={patchConfig} universes={universes} />
      )}
      {node.data.vizaType === "attribute" && (
        <AttributeFields
          attributeOptions={attributeOptions}
          config={config}
          onPatchConfig={patchConfig}
          onPatchNode={patchNode}
        />
      )}
      {node.data.vizaType === "score" && (
        <ScoreFields
          attributeKeys={attributeKeysFromNodes(nodes)}
          attributeOptions={attributeOptions}
          config={config}
          onPatch={patchConfig}
        />
      )}
      {node.data.vizaType === "output_radar" && (
        <OutputRadarFields config={config} onPatch={patchConfig} />
      )}
      {node.data.vizaType === "transform" && (
        <TransformFields config={config} onPatch={patchConfig} />
      )}
      {node.data.vizaType === "filter" && (
        <FilterFields attributeOptions={attributeOptions} config={config} onPatch={patchConfig} />
      )}
      {node.data.vizaType === "relationship" && (
        <RelationshipFields config={config} onPatch={patchConfig} />
      )}

      <div className="node-id">{node.id}</div>
    </aside>
  );
}

function UniverseFields({
  config,
  onPatch,
  universes,
}: {
  config: Record<string, unknown>;
  onPatch: (patch: Record<string, unknown>) => void;
  universes: VizaUniverseSummary[];
}) {
  const selectedUniverseName = readString(config.universe_name, "pilot_sp500_static");
  const selectedUniverseVersion = readString(config.universe_version, "");
  const selectedUniverseKey = `${selectedUniverseName}:${selectedUniverseVersion}`;

  return (
    <>
      <Field label="Universe">
        {universes.length > 0 ? (
          <select
            value={selectedUniverseKey}
            onChange={(event) => {
              const universe = universes.find((item) => item.key === event.target.value);
              if (universe) {
                onPatch({
                  universe_name: universe.universe_name,
                  universe_version: universe.version,
                });
              }
            }}
          >
            {universes.map((universe) => (
              <option key={universe.key} value={universe.key}>
                {universe.display_name} ({universe.asset_count})
              </option>
            ))}
          </select>
        ) : (
          <input
            value={readString(config.universe_name, "pilot_sp500_static")}
            onChange={(event) => onPatch({ universe_name: event.target.value })}
          />
        )}
      </Field>
      <Field label="Version">
        <input
          value={readString(config.universe_version, "")}
          onChange={(event) => onPatch({ universe_version: event.target.value })}
        />
      </Field>
      <Field label="Ticker subset">
        <textarea
          rows={3}
          value={readStringArray(config.ticker_subset).join(", ")}
          onChange={(event) => onPatch({ ticker_subset: parseCsv(event.target.value) })}
        />
      </Field>
    </>
  );
}

function AttributeFields({
  attributeOptions,
  config,
  onPatchConfig,
  onPatchNode,
}: {
  attributeOptions: VizaAttributeDefinition[];
  config: Record<string, unknown>;
  onPatchConfig: (patch: Record<string, unknown>) => void;
  onPatchNode: (patch: Partial<Pick<VizaCanvasNodeData, "label" | "config">>) => void;
}) {
  const attributeKey = readString(config.attribute_key, "unexplained_residual_bps");
  const selectedAttribute =
    attributeOptions.find((attribute) => attribute.key === attributeKey) ??
    findAttribute(attributeKey);
  const [searchText, setSearchText] = useState("");
  const [familyFilter, setFamilyFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [unitFilter, setUnitFilter] = useState("all");
  const [pointInTimeFilter, setPointInTimeFilter] = useState("all");
  const [stageFilter, setStageFilter] = useState("all");
  const [entitlementFilter, setEntitlementFilter] = useState("all");
  const [scoringFilter, setScoringFilter] = useState("all");
  const [favoriteKeys, setFavoriteKeys] = useState(() =>
    readStoredStringArray("viza.favorite_attributes"),
  );
  const [recentKeys, setRecentKeys] = useState(() =>
    readStoredStringArray("viza.recent_attributes"),
  );
  const favoriteAttributes = favoriteKeys
    .map((key) => attributeOptions.find((attribute) => attribute.key === key))
    .filter((attribute): attribute is VizaAttributeDefinition => Boolean(attribute));
  const recentAttributes = recentKeys
    .map((key) => attributeOptions.find((attribute) => attribute.key === key))
    .filter((attribute): attribute is VizaAttributeDefinition => Boolean(attribute));
  const filteredAttributes = attributeOptions
    .filter((attribute) => attributeMatchesSearch(attribute, searchText))
    .filter((attribute) => familyFilter === "all" || attribute.family === familyFilter)
    .filter((attribute) => sourceFilter === "all" || attribute.source === sourceFilter)
    .filter((attribute) => unitFilter === "all" || attribute.unit === unitFilter)
    .filter(
      (attribute) =>
        pointInTimeFilter === "all" || attribute.point_in_time_status === pointInTimeFilter,
    )
    .filter((attribute) => stageFilter === "all" || attribute.contribution_stage === stageFilter)
    .filter((attribute) => {
      if (entitlementFilter === "all") {
        return true;
      }
      if (entitlementFilter === "limited") {
        return isAttributeLocked(attribute);
      }
      return !isAttributeLocked(attribute);
    })
    .filter((attribute) => {
      if (scoringFilter === "all") {
        return true;
      }
      if (scoringFilter === "scoreable") {
        return attribute.production_scoring_allowed === true;
      }
      if (scoringFilter === "evidence_only") {
        return attribute.evidence_only === true || attribute.contribution_stage === "evidence_only";
      }
      return attribute.production_scoring_allowed === false || isAttributeLocked(attribute);
    })
    .slice(0, 18);

  const selectAttribute = (attribute: VizaAttributeDefinition) => {
    onPatchNode({
      label: attribute.display_name,
      config: {
        ...config,
        attribute_key: attribute.key,
      },
    });
    const nextRecentKeys = moveToFront(recentKeys, attribute.key, 6);
    setRecentKeys(nextRecentKeys);
    writeStoredStringArray("viza.recent_attributes", nextRecentKeys);
  };

  const toggleFavorite = (key: string) => {
    const nextFavoriteKeys = toggleStringMembership(favoriteKeys, key);
    setFavoriteKeys(nextFavoriteKeys);
    writeStoredStringArray("viza.favorite_attributes", nextFavoriteKeys);
  };

  return (
    <>
      <Field label="Attribute">
        <div className="attribute-picker">
          <div className="attribute-picker-current">
            <strong>{selectedAttribute?.display_name ?? readableAttributeName(attributeKey)}</strong>
            <span>{selectedAttribute?.description ?? attributeKey}</span>
          </div>
          <div className="attribute-search-row">
            <Search size={16} />
            <input
              aria-label="Search attributes"
              placeholder="Search attributes"
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
            />
          </div>
          <div className="attribute-filter-grid">
            <select
              aria-label="Attribute family"
              value={familyFilter}
              onChange={(event) => setFamilyFilter(event.target.value)}
            >
              <option value="all">All families</option>
              {uniqueAttributeValues(attributeOptions, "family").map((family) => (
                <option key={family} value={family}>
                  {readableHeader(family)}
                </option>
              ))}
            </select>
            <select
              aria-label="Attribute source"
              value={sourceFilter}
              onChange={(event) => setSourceFilter(event.target.value)}
            >
              <option value="all">All sources</option>
              {uniqueAttributeValues(attributeOptions, "source").map((source) => (
                <option key={source} value={source}>
                  {readableHeader(source)}
                </option>
              ))}
            </select>
            <select
              aria-label="Attribute unit"
              value={unitFilter}
              onChange={(event) => setUnitFilter(event.target.value)}
            >
              <option value="all">All units</option>
              {uniqueAttributeValues(attributeOptions, "unit").map((unit) => (
                <option key={unit} value={unit}>
                  {readableHeader(unit)}
                </option>
              ))}
            </select>
            <select
              aria-label="Point in time status"
              value={pointInTimeFilter}
              onChange={(event) => setPointInTimeFilter(event.target.value)}
            >
              <option value="all">All PIT states</option>
              {uniqueAttributeValues(attributeOptions, "point_in_time_status").map((status) => (
                <option key={status} value={status}>
                  {readableHeader(status)}
                </option>
              ))}
            </select>
            <select
              aria-label="Contribution stage"
              value={stageFilter}
              onChange={(event) => setStageFilter(event.target.value)}
            >
              <option value="all">All stages</option>
              {uniqueAttributeValues(attributeOptions, "contribution_stage").map((stage) => (
                <option key={stage} value={stage}>
                  {readableHeader(stage)}
                </option>
              ))}
            </select>
            <select
              aria-label="Entitlement status"
              value={entitlementFilter}
              onChange={(event) => setEntitlementFilter(event.target.value)}
            >
              <option value="all">All entitlements</option>
              <option value="available">Available</option>
              <option value="limited">Limited</option>
            </select>
            <select
              aria-label="Scoring status"
              value={scoringFilter}
              onChange={(event) => setScoringFilter(event.target.value)}
            >
              <option value="all">All scoring states</option>
              <option value="scoreable">Scoreable</option>
              <option value="evidence_only">Evidence-only</option>
              <option value="restricted">Restricted</option>
            </select>
          </div>
          {(favoriteAttributes.length > 0 || recentAttributes.length > 0) && (
            <div className="attribute-chip-area">
              {favoriteAttributes.length > 0 && (
                <AttributeChipRow
                  attributes={favoriteAttributes}
                  label="Pinned"
                  onSelect={selectAttribute}
                />
              )}
              {recentAttributes.length > 0 && (
                <AttributeChipRow
                  attributes={recentAttributes}
                  label="Recent"
                  onSelect={selectAttribute}
                />
              )}
            </div>
          )}
          <div className="attribute-results" role="listbox" aria-label="Matching attributes">
            {filteredAttributes.map((attribute) => {
              const locked = isAttributeLocked(attribute);
              const favorite = favoriteKeys.includes(attribute.key);
              const selected = attribute.key === attributeKey;
              return (
                <div
                  className={`attribute-option-row ${selected ? "selected" : ""} ${
                    locked ? "locked" : ""
                  }`}
                  key={attribute.key}
                >
                  <button
                    aria-selected={selected}
                    className="attribute-option"
                    type="button"
                    role="option"
                    onClick={() => selectAttribute(attribute)}
                  >
                    <span className="attribute-option-main">
                      <strong>{attribute.display_name}</strong>
                      <span>{attribute.description}</span>
                    </span>
                    <span className="attribute-option-meta">
                      {readableHeader(attribute.family)} / {readableHeader(attribute.unit)}
                    </span>
                    <AttributeBadges attribute={attribute} />
                  </button>
                  <button
                    className={`favorite-button ${favorite ? "active" : ""}`}
                    type="button"
                    title={favorite ? "Unpin attribute" : "Pin attribute"}
                    onClick={() => toggleFavorite(attribute.key)}
                  >
                    <Star size={15} fill={favorite ? "currentColor" : "none"} />
                  </button>
                </div>
              );
            })}
            {filteredAttributes.length === 0 && (
              <div className="quiet-note">No attributes match the current filters.</div>
            )}
          </div>
          {selectedAttribute && <AttributeDetail attribute={selectedAttribute} />}
        </div>
      </Field>
      <Field label="Lookback days">
        <input
          min={1}
          type="number"
          value={readNumber(config.lookback_days, 1)}
          onChange={(event) => onPatchConfig({ lookback_days: Number(event.target.value) })}
        />
      </Field>
      <Field label="Missing data">
        <select
          value={readString(config.missing_data, "warn_and_exclude_from_score")}
          onChange={(event) => onPatchConfig({ missing_data: event.target.value })}
        >
          <option value="warn_and_exclude_from_score">Warn and exclude</option>
          <option value="treat_as_zero">Treat as zero</option>
          <option value="require_available">Require available</option>
        </select>
      </Field>
    </>
  );
}

function AttributeChipRow({
  attributes,
  label,
  onSelect,
}: {
  attributes: VizaAttributeDefinition[];
  label: string;
  onSelect: (attribute: VizaAttributeDefinition) => void;
}) {
  return (
    <div className="attribute-chip-row">
      <span>{label}</span>
      {attributes.map((attribute) => (
        <button key={attribute.key} type="button" onClick={() => onSelect(attribute)}>
          {attribute.display_name}
        </button>
      ))}
    </div>
  );
}

function AttributeBadges({ attribute }: { attribute: VizaAttributeDefinition }) {
  const locked = isAttributeLocked(attribute);
  const evidenceOnly =
    attribute.evidence_only === true || attribute.contribution_stage === "evidence_only";
  const sourceBacked = isSourceBackedAttribute(attribute);
  const prototypeFallback = isPrototypeFallbackAttribute(attribute);
  const restrictedExport = isExportRestrictedAttribute(attribute);
  return (
    <span className="attribute-badges">
      {sourceBacked && <span className="attribute-badge source">Source-backed</span>}
      {prototypeFallback && <span className="attribute-badge prototype">Prototype fallback</span>}
      {evidenceOnly && <span className="attribute-badge evidence">Evidence-only</span>}
      {attribute.production_scoring_allowed === true && (
        <span className="attribute-badge scoreable">Scoreable</span>
      )}
      {restrictedExport && <span className="attribute-badge export">Restricted export</span>}
      {locked && (
        <span className="attribute-badge locked">
          <LockKeyhole size={12} />
          Limited
        </span>
      )}
      {attribute.deprecation_status && attribute.deprecation_status !== "active" && (
        <span className="attribute-badge locked">
          {readableHeader(attribute.deprecation_status)}
        </span>
      )}
    </span>
  );
}

function AttributeDetail({ attribute }: { attribute: VizaAttributeDefinition }) {
  const limitations = attribute.limitations ?? [];
  const allowedTransforms = attribute.allowed_transforms ?? [];
  const connectorMappingPath = connectorMappingForAttribute(attribute);

  return (
    <section className="attribute-detail">
      <div>
        <strong>{attribute.display_name}</strong>
        <AttributeBadges attribute={attribute} />
      </div>
      <p>{attribute.description}</p>
      <dl className="attribute-detail-grid">
        <dt>Source</dt>
        <dd>{attribute.source}</dd>
        <dt>Source type</dt>
        <dd>{readableHeader(attribute.source_type ?? "unknown")}</dd>
        <dt>Unit</dt>
        <dd>{readableHeader(attribute.unit)}</dd>
        <dt>Coverage</dt>
        <dd>{attribute.coverage ?? "unspecified"}</dd>
        <dt>Freshness</dt>
        <dd>{attribute.freshness ?? "unspecified"}</dd>
        <dt>Timestamp</dt>
        <dd>{readableHeader(attribute.timestamp_policy ?? attribute.point_in_time_status)}</dd>
        <dt>License</dt>
        <dd>{attribute.license_policy}</dd>
        <dt>Entitlement</dt>
        <dd>{attribute.entitlement_policy ?? "internal"}</dd>
        <dt>Transforms</dt>
        <dd>
          {allowedTransforms.length > 0
            ? allowedTransforms.map((transform) => readableHeader(transform)).join(", ")
            : "None registered"}
        </dd>
      </dl>
      {limitations.length > 0 && (
        <div className="attribute-limitations">
          {limitations.map((limitation) => (
            <span key={limitation}>{limitation}</span>
          ))}
        </div>
      )}
      {connectorMappingPath && (
        <div className="attribute-source-path">
          <strong>Source mapping</strong>
          <span>{connectorMappingPath}</span>
        </div>
      )}
    </section>
  );
}

function ScoreFields({
  attributeKeys,
  attributeOptions,
  config,
  onPatch,
}: {
  attributeKeys: string[];
  attributeOptions: VizaAttributeDefinition[];
  config: Record<string, unknown>;
  onPatch: (patch: Record<string, unknown>) => void;
}) {
  const weights = readNumberRecord(config.weights);
  const scoreKeys = attributeKeys.length > 0 ? attributeKeys : Object.keys(weights);

  return (
    <>
      <Field label="Method">
        <select
          value={readString(config.method, "weighted_sum")}
          onChange={(event) => onPatch({ method: event.target.value })}
        >
          <option value="weighted_sum">Weighted sum</option>
          <option value="average_rank">Average rank</option>
        </select>
      </Field>
      <div className="field-group-label">Weights</div>
      {scoreKeys.length === 0 && (
        <div className="quiet-note">Add Attribute nodes to edit weights.</div>
      )}
      {scoreKeys.map((key) => (
        <Field key={key} label={scoreWeightLabel(key, attributeOptions)}>
          <input
            max={1}
            min={0}
            step={0.05}
            type="number"
            value={weights[key] ?? 0}
            onChange={(event) =>
              onPatch({
                weights: {
                  ...weights,
                  [key]: Number(event.target.value),
                },
              })
            }
          />
        </Field>
      ))}
      <label className="check-field">
        <input
          checked={readBoolean(config.allow_evidence_only)}
          type="checkbox"
          onChange={(event) => onPatch({ allow_evidence_only: event.target.checked })}
        />
        <span>Allow evidence-only score inputs</span>
      </label>
      <Field label="Missing data">
        <select
          value={readString(config.missing_data, "renormalize_available_weights")}
          onChange={(event) => onPatch({ missing_data: event.target.value })}
        >
          <option value="renormalize_available_weights">Renormalize weights</option>
          <option value="require_all_inputs">Require all inputs</option>
          <option value="penalize_missing">Penalize missing</option>
        </select>
      </Field>
    </>
  );
}

function OutputRadarFields({
  config,
  onPatch,
}: {
  config: Record<string, unknown>;
  onPatch: (patch: Record<string, unknown>) => void;
}) {
  return (
    <>
      <Field label="Top N">
        <input
          min={1}
          type="number"
          value={readNumber(config.top_n, 25)}
          onChange={(event) => onPatch({ top_n: Number(event.target.value) })}
        />
      </Field>
      <Field label="Sort">
        <select
          value={readString(config.sort, "descending")}
          onChange={(event) => onPatch({ sort: event.target.value })}
        >
          <option value="descending">Descending</option>
          <option value="ascending">Ascending</option>
        </select>
      </Field>
      <Field label="Columns">
        <textarea
          rows={5}
          value={readStringArray(config.columns).join(", ")}
          onChange={(event) => onPatch({ columns: parseCsv(event.target.value) })}
        />
      </Field>
    </>
  );
}

function TransformFields({
  config,
  onPatch,
}: {
  config: Record<string, unknown>;
  onPatch: (patch: Record<string, unknown>) => void;
}) {
  return (
    <>
      <Field label="Transform">
        <select
          value={readString(config.transform, "percentile_rank")}
          onChange={(event) => onPatch({ transform: event.target.value })}
        >
          <option value="percentile_rank">Percentile rank</option>
          <option value="z_score">Z-score</option>
          <option value="absolute_value">Absolute value</option>
          <option value="trailing_average">Trailing average</option>
        </select>
      </Field>
      <Field label="Direction">
        <select
          value={readString(config.direction, "higher_is_better")}
          onChange={(event) => onPatch({ direction: event.target.value })}
        >
          <option value="higher_is_better">Higher is better</option>
          <option value="lower_is_better">Lower is better</option>
        </select>
      </Field>
    </>
  );
}

function FilterFields({
  attributeOptions,
  config,
  onPatch,
}: {
  attributeOptions: VizaAttributeDefinition[];
  config: Record<string, unknown>;
  onPatch: (patch: Record<string, unknown>) => void;
}) {
  return (
    <>
      <Field label="Attribute">
        <select
          value={readString(config.attribute_key, "unexplained_residual_bps")}
          onChange={(event) => onPatch({ attribute_key: event.target.value })}
        >
          {attributeOptions.map((attribute) => (
            <option key={attribute.key} value={attribute.key}>
              {attribute.display_name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Operator">
        <select
          value={readString(config.operator, "is_available")}
          onChange={(event) => onPatch({ operator: event.target.value })}
        >
          <option value="is_available">Is available</option>
          <option value="greater_than">Greater than</option>
          <option value="less_than">Less than</option>
          <option value="between">Between</option>
        </select>
      </Field>
      <Field label="Value">
        <input
          value={readString(config.value, "")}
          onChange={(event) => onPatch({ value: event.target.value })}
        />
      </Field>
    </>
  );
}

function RelationshipFields({
  config,
  onPatch,
}: {
  config: Record<string, unknown>;
  onPatch: (patch: Record<string, unknown>) => void;
}) {
  return (
    <Field label="Relationships">
      <textarea
        rows={5}
        value={readStringArray(config.relationships).join(", ")}
        onChange={(event) => onPatch({ relationships: parseCsv(event.target.value) })}
      />
    </Field>
  );
}

function Field({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function ResultPanel({
  attributeCount,
  connectors,
  desktopStatus,
  diagnostics,
  engineStatus,
  metadataError,
  metadataSource,
  batchResult,
  runtimeJob,
  runtimeJobEvents,
  buildMethodologyGraph,
  isBatchRunning,
  isRestartingEngine,
  isRunning,
  project,
  result,
  versionDiff,
  versions,
  universeCount,
  onCloneVersion,
  onApplyGraph,
  onLoadVersion,
  onRefreshDiagnostics,
  onRevertVersion,
  onRestartEngine,
  onRunBatch,
  onCancelRuntimeJob,
  onSelectBatchRun,
  onSaveVersion,
}: {
  attributeCount: number;
  connectors: VizaConnectorDefinition[];
  desktopStatus: VizaDesktopStatus | null;
  diagnostics: VizaRuntimeDiagnostics | null;
  engineStatus: EngineStatus;
  metadataError: string | null;
  metadataSource: MetadataSource;
  batchResult: VizaBatchExecutionResult | null;
  runtimeJob: VizaRuntimeJobRecord | null;
  runtimeJobEvents: VizaRuntimeJobEvent[];
  buildMethodologyGraph: () => VizaMethodologyGraph;
  isBatchRunning: boolean;
  isRestartingEngine: boolean;
  isRunning: boolean;
  project: VizaProjectSummary | null;
  result: MethodologyRunResult | null;
  versionDiff: VizaMethodologyVersionDiff | null;
  versions: VizaMethodologyVersionSummary[];
  universeCount: number;
  onApplyGraph: (graph: VizaMethodologyGraph) => void;
  onCloneVersion: (version: VizaMethodologyVersionSummary) => void;
  onLoadVersion: (version: VizaMethodologyVersionSummary) => void;
  onRefreshDiagnostics: () => void;
  onRevertVersion: (version: VizaMethodologyVersionSummary) => void;
  onRestartEngine: () => void;
  onRunBatch: (cutoffs: string[], tickerSubset: string[]) => void;
  onCancelRuntimeJob: () => void;
  onSelectBatchRun: (result: MethodologyRunResult) => void;
  onSaveVersion: () => void;
}) {
  const graphEvidence = isRecord(result?.evidence.graph) ? result.evidence.graph : null;
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [selectedEvidenceRef, setSelectedEvidenceRef] = useState<string | null>(null);
  const allAttributeColumns = useMemo(() => resultAttributeColumns(result), [result]);
  const [visibleAttributeColumns, setVisibleAttributeColumns] = useState<string[]>([]);
  const [radarFilterText, setRadarFilterText] = useState("");
  const [radarSortKey, setRadarSortKey] = useState("rank");
  const [radarSortDirection, setRadarSortDirection] = useState<RadarSortDirection>("ascending");
  const [radarInsightFilters, setRadarInsightFilters] = useState<RadarInsightFilters>({
    insightType: "all",
    minConfidence: "",
    minStrategyFitScore: "",
    missingConfirmation: "all",
    pitStatus: "all",
    riskFlag: "all",
    sourceRestriction: "all",
  });
  const [showEvidenceColumn, setShowEvidenceColumn] = useState(false);
  const displayedRows = useMemo(
    () =>
      designRadarRows(
        result?.rows ?? [],
        radarFilterText,
        radarSortKey,
        radarSortDirection,
        radarInsightFilters,
      ),
    [radarFilterText, radarInsightFilters, radarSortDirection, radarSortKey, result?.rows],
  );
  const selectedRow = result?.rows.find((row) => row.ticker === selectedTicker) ?? null;
  const insightFilterOptions = useMemo(
    () => buildRadarInsightFilterOptions(result?.rows ?? []),
    [result?.rows],
  );

  useEffect(() => {
    const firstTicker = result?.rows[0]?.ticker ?? null;
    setSelectedTicker(firstTicker);
    setSelectedEvidenceRef(firstTicker ? `company:${firstTicker}` : null);
  }, [result?.run_id, result?.rows]);

  useEffect(() => {
    setVisibleAttributeColumns(resultAttributeColumns(result).slice(0, 6));
    setRadarFilterText("");
    setRadarSortKey("rank");
    setRadarSortDirection("ascending");
    setRadarInsightFilters({
      insightType: "all",
      minConfidence: "",
      minStrategyFitScore: "",
      missingConfirmation: "all",
      pitStatus: "all",
      riskFlag: "all",
      sourceRestriction: "all",
    });
    setShowEvidenceColumn(false);
  }, [result?.run_id, result]);

  return (
    <section className="result-panel">
      <div className="result-summary">
        <span className={`result-status ${result?.status ?? engineStatus}`}>
          {isRunning ? "running" : result?.status ?? engineStatus}
        </span>
        <span>{metadataSource === "engine" ? `${attributeCount} attributes` : `fallback ${attributeCount} attributes`}</span>
        <span>{metadataError && universeCount === 0 ? "universes unavailable" : `${universeCount} universes`}</span>
        <span>{metadataError && connectors.length === 0 ? "connectors unavailable" : `${connectors.length} connectors`}</span>
        {metadataError && <span title={metadataError}>metadata incomplete</span>}
        {result && <span>{result.run_id}</span>}
      </div>
      <div className="result-body">
        <div className="result-column radar-column">
          <div className="result-label">Radar</div>
          {displayedRows.length ? (
            <table className="radar-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Ticker</th>
                  <th>Score</th>
                  <th>Fit</th>
                  <th>Insight</th>
                  <th>Summary</th>
                  {visibleAttributeColumns.map((column) => (
                    <th key={column}>{readableHeader(column)}</th>
                  ))}
                  {showEvidenceColumn && <th>Evidence</th>}
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {displayedRows.map((row) => (
                  <tr
                    className={row.ticker === selectedTicker ? "selected-radar-row" : ""}
                    key={row.ticker}
                    onClick={() => {
                      setSelectedTicker(row.ticker);
                      setSelectedEvidenceRef(`company:${row.ticker}`);
                    }}
                  >
                    <td>{row.rank}</td>
                    <td>
                      <strong>{row.ticker}</strong>
                      <span>{row.company_name}</span>
                    </td>
                    <td>{formatCell(row.score)}</td>
                    <td>
                      <StrategyFitBadge
                        action={row.translated_summary ?? null}
                        score={row.strategy_fit_score ?? null}
                      />
                    </td>
                    <td>{row.primary_insight_type ? readableHeader(row.primary_insight_type) : "-"}</td>
                    <td>{row.translated_summary ?? "-"}</td>
                    {visibleAttributeColumns.map((column) => (
                      <td key={column}>{formatCell(row.attributes[column])}</td>
                    ))}
                    {showEvidenceColumn && <td>{row.evidence_refs.length}</td>}
                    <td>{row.warnings.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="result-empty">No radar rows.</div>
          )}
        </div>
        <RelationshipView
          evidence={result?.evidence ?? {}}
          relationships={result?.relationships ?? []}
          row={selectedRow}
          selectedEvidenceRef={selectedEvidenceRef}
          onEvidenceSelect={setSelectedEvidenceRef}
        />
        <div className="result-column side-result-column">
          <InsightCardsPanel
            result={result}
            row={selectedRow}
            selectedEvidenceRef={selectedEvidenceRef}
            onEvidenceSelect={setSelectedEvidenceRef}
          />
          <DecisionsPanel runId={result?.run_id ?? null} />
          <div className="result-label">Warnings</div>
          {result?.warnings.length ? (
            <ul className="warning-list">
              {result.warnings.map((warning) => (
                <li key={`${warning.code}-${warning.node_id ?? "graph"}`}>
                  <strong>{warning.code}</strong>
                  <span>{warning.message}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="result-empty">No run warnings.</div>
          )}
          <RuntimeJobPanel
            events={runtimeJobEvents}
            job={runtimeJob}
            onCancel={onCancelRuntimeJob}
          />
          <DiagnosticsPanel
            desktopStatus={desktopStatus}
            diagnostics={diagnostics}
            engineStatus={engineStatus}
            isRestartingEngine={isRestartingEngine}
            onRefresh={onRefreshDiagnostics}
            onRestart={onRestartEngine}
          />
          <EquityRuntimePreviewPanel />
          <ProjectVersionPanel
            diff={versionDiff}
            project={project}
            versions={versions}
            onCloneVersion={onCloneVersion}
            onLoadVersion={onLoadVersion}
            onRevertVersion={onRevertVersion}
            onSaveVersion={onSaveVersion}
          />
          <FileExchangePanel
            buildMethodologyGraph={buildMethodologyGraph}
            project={project}
            result={result}
            onApplyGraph={onApplyGraph}
          />
          <BatchPanel
            batchResult={batchResult}
            isBatchRunning={isBatchRunning}
            onRunBatch={onRunBatch}
            onSelectBatchRun={onSelectBatchRun}
          />
          <RadarDesignerPanel
            allAttributeColumns={allAttributeColumns}
            buildMethodologyGraph={buildMethodologyGraph}
            displayedRows={displayedRows}
            filterText={radarFilterText}
            insightFilters={radarInsightFilters}
            insightFilterOptions={insightFilterOptions}
            project={project}
            result={result}
            selectedColumns={visibleAttributeColumns}
            showEvidenceColumn={showEvidenceColumn}
            sortDirection={radarSortDirection}
            sortKey={radarSortKey}
            versionId={versions[0]?.version_id ?? null}
            onFilterTextChange={setRadarFilterText}
            onInsightFiltersChange={setRadarInsightFilters}
            onSelectedColumnsChange={setVisibleAttributeColumns}
            onShowEvidenceColumnChange={setShowEvidenceColumn}
            onSortDirectionChange={setRadarSortDirection}
            onSortKeyChange={setRadarSortKey}
          />
          <div className="result-label">Payload</div>
          <dl className="payload-grid">
            <dt>Rows</dt>
            <dd>{result?.rows.length ?? 0}</dd>
            <dt>Relationships</dt>
            <dd>{result?.relationships.length ?? 0}</dd>
            <dt>Attributes</dt>
            <dd>{readStringArray(graphEvidence?.attribute_keys).length}</dd>
          </dl>
          <AuditPanel result={result} />
          <ValidationPanel result={result} />
          <ConnectorPanel connectors={connectors} manifest={result?.manifest ?? {}} />
          <EvidenceInspector
            evidence={result?.evidence ?? {}}
            evidenceRef={selectedEvidenceRef}
            relationships={result?.relationships ?? []}
          />
        </div>
      </div>
    </section>
  );
}

function RelationshipView({
  evidence,
  relationships,
  row,
  selectedEvidenceRef,
  onEvidenceSelect,
}: {
  evidence: Record<string, unknown>;
  relationships: VizaRelationshipEdge[];
  row: VizaRadarRow | null;
  selectedEvidenceRef: string | null;
  onEvidenceSelect: (evidenceRef: string | null) => void;
}) {
  const [familyFilter, setFamilyFilter] = useState("all");
  const [objectTypeFilter, setObjectTypeFilter] = useState("all");
  const [minimumWeight, setMinimumWeight] = useState(0);
  const [searchText, setSearchText] = useState("");

  if (!row) {
    return (
      <div className="relationship-panel">
        <div className="result-label">Relationship</div>
        <div className="result-empty">No selected company.</div>
      </div>
    );
  }

  const companyRef = `company:${row.ticker}`;
  const centerRefs = new Set(
    [companyRef, row.entity_id ?? "", row.asset_id ?? ""].filter((value) => value.length > 0),
  );
  const companyEdges = relationships.filter(
    (edge) =>
      centerRefs.has(edge.source) ||
      centerRefs.has(edge.target) ||
      centerRefs.has(edge.source_id ?? "") ||
      centerRefs.has(edge.target_id ?? ""),
  );
  const relationshipFamilies = Array.from(
    new Set(companyEdges.map((edge) => edge.family || edge.relationship_family || "unknown")),
  ).sort();
  const objectTypes = Array.from(
    new Set(
      companyEdges
        .flatMap((edge) => [edge.source_type, edge.target_type])
        .filter((value): value is string => typeof value === "string" && value.length > 0),
    ),
  ).sort();
  const normalizedSearchText = searchText.trim().toLowerCase();
  const relatedEdges = companyEdges
    .filter(
      (edge) =>
        familyFilter === "all" ||
        edge.relationship_family === familyFilter ||
        edge.family === familyFilter,
    )
    .filter(
      (edge) =>
        objectTypeFilter === "all" ||
        edge.source_type === objectTypeFilter ||
        edge.target_type === objectTypeFilter,
    )
    .filter((edge) => edge.weight === null || Math.abs(edge.weight) >= minimumWeight)
    .filter((edge) => {
      if (!normalizedSearchText) {
        return true;
      }
      return `${edge.source} ${edge.target} ${edge.relationship_type}`
        .toLowerCase()
        .includes(normalizedSearchText);
    })
    .slice(0, 18);
  const graphNodes = buildRelationshipGraphNodes(row, relatedEdges, centerRefs);

  return (
    <div className="relationship-panel">
      <div className="relationship-header">
        <div>
          <div className="result-label">Relationship</div>
          <strong>{row.ticker}</strong>
          <span>{row.company_name}</span>
        </div>
        <button
          className="evidence-chip"
          type="button"
          onClick={() => onEvidenceSelect(companyRef)}
        >
          company
        </button>
      </div>
      <div className="relationship-filters">
        <select
          aria-label="Relationship family"
          value={familyFilter}
          onChange={(event) => setFamilyFilter(event.target.value)}
        >
          <option value="all">All families</option>
          {relationshipFamilies.map((family) => (
            <option key={family} value={family}>
              {readableHeader(family)}
            </option>
          ))}
        </select>
        <select
          aria-label="Relationship object type"
          value={objectTypeFilter}
          onChange={(event) => setObjectTypeFilter(event.target.value)}
        >
          <option value="all">All objects</option>
          {objectTypes.map((objectType) => (
            <option key={objectType} value={objectType}>
              {readableHeader(objectType)}
            </option>
          ))}
        </select>
        <input
          aria-label="Minimum edge strength"
          min={0}
          max={1}
          step={0.05}
          type="number"
          value={minimumWeight}
          onChange={(event) => setMinimumWeight(Number(event.target.value))}
        />
        <input
          aria-label="Search relationships"
          placeholder="Search"
          value={searchText}
          onChange={(event) => setSearchText(event.target.value)}
        />
      </div>
      <svg className="relationship-graph" role="img" viewBox="0 0 520 220">
        {relatedEdges.map((edge) => {
          const source = graphNodes.find((node) => node.id === edge.source) ?? graphNodes[0];
          const target = graphNodes.find((node) => node.id === edge.target);
          if (!source || !target) {
            return null;
          }

          const evidenceRef = edge.evidence_ref ?? edge.target;
          const isSelected = selectedEvidenceRef === evidenceRef;
          return (
            <g key={`${edge.source}-${edge.target}-${edge.relationship_type}`}>
              <line
                className={`relationship-line ${isSelected ? "selected" : ""}`}
                x1={source.x}
                x2={target.x}
                y1={source.y}
                y2={target.y}
                onClick={() => onEvidenceSelect(evidenceRef)}
              />
              <circle
                className={`relationship-edge-hit ${isSelected ? "selected" : ""}`}
                cx={(source.x + target.x) / 2}
                cy={(source.y + target.y) / 2}
                r="7"
                onClick={() => onEvidenceSelect(evidenceRef)}
              />
              <text
                className="relationship-edge-label"
                x={(source.x + target.x) / 2}
                y={(source.y + target.y) / 2 - 10}
              >
                {edgeLabel(edge)}
              </text>
            </g>
          );
        })}
        {graphNodes.map((node) => (
          <g
            className={`relationship-node ${node.kind} ${
              selectedEvidenceRef === node.evidenceRef ? "selected" : ""
            }`}
            key={node.id}
            role="button"
            tabIndex={0}
            transform={`translate(${node.x}, ${node.y})`}
            onClick={() => onEvidenceSelect(node.evidenceRef)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onEvidenceSelect(node.evidenceRef);
              }
            }}
          >
            <circle r={node.kind === "entity" ? 28 : 20} />
            <text y={node.kind === "entity" ? 4 : 3}>{shortGraphLabel(node.label)}</text>
          </g>
        ))}
      </svg>
      <div className="relationship-edge-list">
        {relatedEdges.map((edge) => {
          const evidenceRef = edge.evidence_ref ?? edge.target;
          const detail = evidenceRef ? evidence[evidenceRef] : null;
          return (
            <button
              className={selectedEvidenceRef === evidenceRef ? "selected" : ""}
              key={`${edge.source}-${edge.target}-${edge.relationship_type}`}
              type="button"
              onClick={() => onEvidenceSelect(evidenceRef)}
            >
              <span>
                {readableHeader(edge.family || edge.relationship_family)} /{" "}
                {readableHeader(edge.relationship_type)}
              </span>
              <strong>{relationshipTargetLabel(edge, detail)}</strong>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function FileExchangePanel({
  buildMethodologyGraph,
  project,
  result,
  onApplyGraph,
}: {
  buildMethodologyGraph: () => VizaMethodologyGraph;
  project: VizaProjectSummary | null;
  result: MethodologyRunResult | null;
  onApplyGraph: (graph: VizaMethodologyGraph) => void;
}) {
  const [targetPath, setTargetPath] = useState("");
  const [selectedPath, setSelectedPath] = useState("");
  const [visualization, setVisualization] = useState<VizaFileVisualization | null>(null);
  const [fileRecords, setFileRecords] = useState<VizaFileRecordResponse[]>([]);
  const [fileStatus, setFileStatus] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const currentGraph = buildMethodologyGraph();

  const refreshFileRecords = useCallback(async () => {
    const records = await fetchVizaFileRecords();
    setFileRecords(records);
  }, []);

  useEffect(() => {
    void refreshFileRecords().catch(() => undefined);
  }, [refreshFileRecords]);

  const runFileAction = async (action: () => Promise<string>) => {
    setIsBusy(true);
    try {
      setFileStatus(await action());
    } catch (error) {
      setFileStatus(error instanceof Error ? error.message : "VIZA file action failed.");
    } finally {
      setIsBusy(false);
    }
  };

  const chooseExportPath = async (defaultName = `${slugify(currentGraph.name)}.viza`) => {
    if (!window.vizaDesktop?.selectExportPath) {
      setFileStatus("Desktop export path picker is unavailable.");
      return null;
    }
    const selected = await window.vizaDesktop.selectExportPath(defaultName);
    if (selected.canceled || !selected.path) {
      return null;
    }
    setTargetPath(selected.path);
    return selected.path;
  };

  const inspectPath = async (path: string) => {
    const inspection = await inspectVizaFile(path);
    setSelectedPath(path);
    setVisualization(inspection.visualization ?? null);
    return inspection;
  };

  const chooseVizaFile = () =>
    runFileAction(async () => {
      if (!window.vizaDesktop?.selectVizaFile) {
        return "Desktop file picker is unavailable.";
      }
      const selected = await window.vizaDesktop.selectVizaFile();
      if (selected.canceled || !selected.path) {
        return "Open canceled.";
      }
      const inspection = await inspectPath(selected.path);
      return inspection.visualization
        ? `Opened ${inspection.visualization.file_id}.`
        : "Opened file without visualization.";
    });

  const exportFile = (request: VizaFileExportRequest) =>
    runFileAction(async () => {
      const path = targetPath || (await chooseExportPath(`${slugify(currentGraph.name)}.viza`));
      if (!path) {
        return "Export canceled.";
      }
      const includeRunReference =
        request.include_validation_proof || request.purpose === "marketplace_draft";
      const exported = await exportVizaFile({
        ...request,
        graph: currentGraph,
        target_path: path,
        project_id: project?.project_id ?? request.project_id ?? null,
        run_id: includeRunReference ? result?.run_id ?? null : request.run_id ?? null,
        source_rights: sourceRightsFromRunResult(result),
      });
      const inspection = await inspectPath(path);
      await refreshFileRecords();
      return inspection.visualization
        ? `Exported ${inspection.visualization.file_id}.`
        : `Exported ${exported.result.file_id}.`;
    });

  const importSelectedFile = (mode: NonNullable<VizaFileImportRequest["mode"]>) =>
    runFileAction(async () => {
      if (!selectedPath) {
        return "Open a .viza file first.";
      }
      const imported = await importVizaFile({
        path: selectedPath,
        project_id: project?.project_id ?? null,
        mode,
        save_methodology_version: mode === "import_to_project" || mode === "fork_as_new_methodology",
        label: mode === "fork_as_new_methodology" ? "Forked .viza import" : "Imported .viza file",
        message: `Imported through VIZA desktop as ${mode}.`,
      });
      if (imported.graph) {
        onApplyGraph(imported.graph);
      }
      await refreshFileRecords();
      return imported.methodology_version
        ? `${readableHeader(imported.status)} and saved version.`
        : readableHeader(imported.status);
    });

  return (
    <section className="file-exchange-panel">
      <div className="result-label">.viza Exchange</div>
      <div className="file-exchange-actions">
        <button type="button" disabled={isBusy} onClick={() => void chooseExportPath()}>
          <FolderOpen size={13} />
          <span>Path</span>
        </button>
        <button type="button" disabled={isBusy} onClick={chooseVizaFile}>
          <FolderOpen size={13} />
          <span>Open</span>
        </button>
      </div>
      <dl className="payload-grid">
        <dt>Target</dt>
        <dd>{targetPath ? compactPath(targetPath) : "not selected"}</dd>
        <dt>Selected</dt>
        <dd>{selectedPath ? compactPath(selectedPath) : "none"}</dd>
      </dl>
      <VizaExportWizard
        graph={currentGraph}
        targetPath={targetPath || `${slugify(currentGraph.name)}.viza`}
        projectId={project?.project_id ?? null}
        onExport={exportFile}
      />
      <StrategyExchangeInbox records={fileRecords} />
      {visualization ? (
        <>
          <VizaFileViewer visualization={visualization} />
          <div className="file-exchange-actions">
            <button
              type="button"
              disabled={isBusy || !visualization.available_actions.includes("open_without_import")}
              onClick={() => importSelectedFile("open_without_import")}
            >
              <FolderOpen size={13} />
              <span>Open</span>
            </button>
            <button
              type="button"
              disabled={isBusy || !visualization.available_actions.includes("import_to_project")}
              onClick={() => importSelectedFile("import_to_project")}
            >
              <Save size={13} />
              <span>Import</span>
            </button>
            <button
              type="button"
              disabled={
                isBusy || !visualization.available_actions.includes("fork_as_new_methodology")
              }
              onClick={() => importSelectedFile("fork_as_new_methodology")}
            >
              <GitBranch size={13} />
              <span>Fork</span>
            </button>
            <button type="button" disabled={isBusy} onClick={() => importSelectedFile("quarantine")}>
              <LockKeyhole size={13} />
              <span>Quarantine</span>
            </button>
          </div>
        </>
      ) : (
        <div className="result-empty">No .viza package selected.</div>
      )}
      {fileStatus && <div className="surface-status">{fileStatus}</div>}
    </section>
  );
}

function BatchPanel({
  batchResult,
  isBatchRunning,
  onRunBatch,
  onSelectBatchRun,
}: {
  batchResult: VizaBatchExecutionResult | null;
  isBatchRunning: boolean;
  onRunBatch: (cutoffs: string[], tickerSubset: string[]) => void;
  onSelectBatchRun: (result: MethodologyRunResult) => void;
}) {
  const [cutoffText, setCutoffText] = useState("2026-05-06, 2026-05-12");
  const [tickerText, setTickerText] = useState("");
  const cutoffs = useMemo(() => parseCsv(cutoffText), [cutoffText]);
  const tickerSubset = useMemo(
    () => parseCsv(tickerText).map((ticker) => ticker.toUpperCase()),
    [tickerText],
  );
  const displayedResults = batchResult?.results.slice(0, 5) ?? [];
  const displayedProgress = batchResult?.progress.slice(-5) ?? [];

  return (
    <section className="batch-panel">
      <div className="result-label">Backtest</div>
      <div className="batch-controls">
        <label>
          <span>Cutoffs</span>
          <input
            aria-label="Batch cutoffs"
            value={cutoffText}
            onChange={(event) => setCutoffText(event.target.value)}
          />
        </label>
        <label>
          <span>Tickers</span>
          <input
            aria-label="Batch ticker subset"
            placeholder="optional"
            value={tickerText}
            onChange={(event) => setTickerText(event.target.value)}
          />
        </label>
        <button
          type="button"
          disabled={isBatchRunning || cutoffs.length === 0}
          onClick={() => onRunBatch(cutoffs, tickerSubset)}
        >
          <Play size={13} />
          <span>{isBatchRunning ? "Running" : "Run"}</span>
        </button>
      </div>
      {batchResult ? (
        <>
          <dl className="batch-summary-grid">
            <dt>Status</dt>
            <dd>{readableHeader(batchResult.status)}</dd>
            <dt>Runs</dt>
            <dd>
              {batchResult.completed_runs}/{batchResult.total_runs}
              {batchResult.failed_runs ? `, ${batchResult.failed_runs} failed` : ""}
            </dd>
          </dl>
          <div className="batch-run-list">
            {displayedResults.map((item) => (
              <button
                key={`${item.sequence}-${item.cutoff}`}
                type="button"
                disabled={!item.result}
                onClick={() => {
                  if (item.result) {
                    onSelectBatchRun(item.result);
                  }
                }}
              >
                <span>
                  <strong>{item.cutoff}</strong>
                  <small>{readableHeader(item.status)}</small>
                </span>
                <span>
                  <strong>{item.diagnostics.top_ticker ?? "-"}</strong>
                  <small>{item.diagnostics.row_count} rows</small>
                </span>
                <span>
                  <strong>{readableHeader(item.pit_status)}</strong>
                  <small>{item.diagnostics.pit_violation_count} PIT</small>
                </span>
              </button>
            ))}
          </div>
          {displayedProgress.length > 0 && (
            <div className="batch-progress-list">
              {displayedProgress.map((event) => (
                <span key={`${event.sequence}-${event.status}-${event.run_id ?? ""}`}>
                  {event.sequence}/{event.total} {readableHeader(event.status)}
                </span>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="result-empty">No batch runs.</div>
      )}
    </section>
  );
}

function RadarDesignerPanel({
  allAttributeColumns,
  buildMethodologyGraph,
  displayedRows,
  filterText,
  insightFilters,
  insightFilterOptions,
  project,
  result,
  selectedColumns,
  showEvidenceColumn,
  sortDirection,
  sortKey,
  versionId,
  onFilterTextChange,
  onInsightFiltersChange,
  onSelectedColumnsChange,
  onShowEvidenceColumnChange,
  onSortDirectionChange,
  onSortKeyChange,
}: {
  allAttributeColumns: string[];
  buildMethodologyGraph: () => VizaMethodologyGraph;
  displayedRows: VizaRadarRow[];
  filterText: string;
  insightFilters: RadarInsightFilters;
  insightFilterOptions: Record<keyof Omit<RadarInsightFilters, "minConfidence" | "minStrategyFitScore">, string[]>;
  project: VizaProjectSummary | null;
  result: MethodologyRunResult | null;
  selectedColumns: string[];
  showEvidenceColumn: boolean;
  sortDirection: "ascending" | "descending";
  sortKey: string;
  versionId: string | null;
  onFilterTextChange: (value: string) => void;
  onInsightFiltersChange: (value: RadarInsightFilters) => void;
  onSelectedColumnsChange: (value: string[]) => void;
  onShowEvidenceColumnChange: (value: boolean) => void;
  onSortDirectionChange: (value: "ascending" | "descending") => void;
  onSortKeyChange: (value: string) => void;
}) {
  const [surfaceStatus, setSurfaceStatus] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [alertType, setAlertType] = useState("score_crosses_threshold");
  const [alertThreshold, setAlertThreshold] = useState(0.8);
  const [alertTopN, setAlertTopN] = useState(10);
  const [scheduleCadence, setScheduleCadence] = useState<
    "manual" | "daily" | "weekly" | "on_app_start"
  >("manual");
  const [lastSavedRadarId, setLastSavedRadarId] = useState<string | null>(null);
  const exportColumns = useMemo(
    () => [
      "ticker",
      "company_name",
      "score",
      "rank",
      "strategy_fit_score",
      "primary_insight_type",
      "translated_summary",
      "confidence",
      "missing_confirmations",
      "invalidation_conditions",
      "risk_flags",
      "evidence_count",
      "source_restrictions",
      "PIT_status",
      ...selectedColumns,
      ...(showEvidenceColumn ? ["evidence_refs"] : []),
    ],
    [selectedColumns, showEvidenceColumn],
  );
  const scorecard = radarScorecard(displayedRows);

  const runSurfaceAction = async (action: () => Promise<string>) => {
    setIsBusy(true);
    try {
      const message = await action();
      setSurfaceStatus(message);
    } catch (error) {
      setSurfaceStatus(error instanceof Error ? error.message : "Research surface action failed.");
    } finally {
      setIsBusy(false);
    }
  };

  const saveCurrentRadar = async () => {
    if (!project || !result) {
      throw new Error("Run a methodology and load a project first.");
    }
    const saved = await saveVizaRadarOutput({
      projectId: project.project_id,
      result,
      name: `${result.methodology_id} radar`,
      selectedColumns: exportColumns,
      displayedTickers: displayedRows.map((row) => row.ticker),
      designer: {
        filter: filterText,
        sort_key: sortKey,
        sort_direction: sortDirection,
        show_evidence_column: showEvidenceColumn,
      },
      versionId,
    });
    setLastSavedRadarId(saved.radar_id);
    return saved;
  };

  const saveRadar = () =>
    runSurfaceAction(async () => {
      const saved = await saveCurrentRadar();
      return `Saved radar ${shortVersionId(saved.radar_id)}.`;
    });

  const saveSchedule = () =>
    runSurfaceAction(async () => {
      if (!project || !result) {
        return "Run a methodology and load a project first.";
      }
      const radarId = lastSavedRadarId ?? (await saveCurrentRadar()).radar_id;
      const schedule = await saveVizaRadarSchedule({
        projectId: project.project_id,
        request: {
          radar_id: radarId,
          methodology_id: result.methodology_id,
          cadence: scheduleCadence,
          enabled: scheduleCadence !== "manual",
          definition: {
            source: "desktop",
            selected_columns: exportColumns,
          },
        },
      });
      return `Saved ${readableHeader(schedule.cadence)} schedule.`;
    });

  const createWatchlist = () =>
    runSurfaceAction(async () => {
      if (!project || !result) {
        return "Run a methodology and load a project first.";
      }
      const watchlist = await createVizaWatchlist({
        projectId: project.project_id,
        name: `${result.methodology_id} watchlist`,
        tickers: displayedRows.map((row) => row.ticker),
        sourceRunId: result.run_id,
      });
      return `Created watchlist ${shortVersionId(watchlist.watchlist_id)}.`;
    });

  const createAlert = () =>
    runSurfaceAction(async () => {
      if (!project) {
        return "Load a project first.";
      }
      const definition: VizaAlertDefinition = {
        alert_type: alertType,
        operator: "greater_than",
        threshold: alertType === "score_crosses_threshold" ? alertThreshold : null,
        top_n: alertType === "rank_enters_top_n" ? alertTopN : null,
        attribute_key:
          alertType === "event_materiality_above_threshold"
            ? "event_materiality"
            : alertType === "residual_above_threshold"
              ? "unexplained_residual_bps"
              : null,
        relationship_type: alertType === "relationship_edge_appears" ? "selected_attribute" : null,
        severity: "info",
      };
      const alert = await createVizaAlert({
        projectId: project.project_id,
        name: readableHeader(alertType),
        definition,
      });
      return `Created alert ${shortVersionId(alert.alert_id)}.`;
    });

  const exportSurface = (exportFormat: VizaExportFormat) =>
    runSurfaceAction(async () => {
      if (exportFormat !== "methodology" && !result) {
        return "Run a methodology first.";
      }
      const exported = await exportVizaPayload({
        export_format: exportFormat,
        result: exportFormat === "csv" || exportFormat === "json" ? result : null,
        graph: exportFormat === "methodology" ? buildMethodologyGraph() : null,
        manifest: exportFormat === "manifest" ? result?.manifest ?? {} : null,
        selected_columns: exportColumns,
        include_evidence: exportFormat === "json",
      });
      downloadText(exported.filename, exported.payload, exported.content_type);
      return exported.redactions.length
        ? `Exported with ${exported.redactions.length} redactions.`
        : `Exported ${exported.filename}.`;
    });

  return (
    <section className="radar-designer-panel">
      <div className="result-label">Designer</div>
      <div className="designer-scorecards">
        <span>
          <strong>{displayedRows.length}</strong>
          <small>Rows</small>
        </span>
        <span>
          <strong>{scorecard.averageScore}</strong>
          <small>Avg score</small>
        </span>
        <span>
          <strong>{scorecard.topTicker}</strong>
          <small>Top</small>
        </span>
      </div>
      <div className="designer-controls">
        <input
          aria-label="Filter radar rows"
          placeholder="Filter"
          value={filterText}
          onChange={(event) => onFilterTextChange(event.target.value)}
        />
        <select
          aria-label="Radar sort column"
          value={sortKey}
          onChange={(event) => onSortKeyChange(event.target.value)}
        >
          <option value="rank">Rank</option>
          <option value="ticker">Ticker</option>
          <option value="score">Score</option>
          <option value="strategy_fit_score">Strategy fit</option>
          <option value="primary_insight_type">Insight type</option>
          <option value="confidence">Confidence</option>
          <option value="PIT_status">PIT status</option>
          {allAttributeColumns.map((column) => (
            <option key={column} value={column}>
              {readableHeader(column)}
            </option>
          ))}
        </select>
        <select
          aria-label="Radar sort direction"
          value={sortDirection}
          onChange={(event) =>
            onSortDirectionChange(event.target.value === "descending" ? "descending" : "ascending")
          }
        >
          <option value="ascending">Ascending</option>
          <option value="descending">Descending</option>
        </select>
      </div>
      <div className="designer-filter-grid">
        <input
          aria-label="Minimum strategy fit score"
          min={0}
          max={1}
          placeholder="Min fit"
          step={0.05}
          type="number"
          value={insightFilters.minStrategyFitScore}
          onChange={(event) =>
            onInsightFiltersChange({
              ...insightFilters,
              minStrategyFitScore: event.target.value,
            })
          }
        />
        <input
          aria-label="Minimum insight confidence"
          min={0}
          max={1}
          placeholder="Min confidence"
          step={0.05}
          type="number"
          value={insightFilters.minConfidence}
          onChange={(event) =>
            onInsightFiltersChange({
              ...insightFilters,
              minConfidence: event.target.value,
            })
          }
        />
        <select
          aria-label="Insight type filter"
          value={insightFilters.insightType}
          onChange={(event) =>
            onInsightFiltersChange({ ...insightFilters, insightType: event.target.value })
          }
        >
          <option value="all">All insights</option>
          {insightFilterOptions.insightType.map((value) => (
            <option key={value} value={value}>
              {readableHeader(value)}
            </option>
          ))}
        </select>
        <select
          aria-label="Missing confirmation filter"
          value={insightFilters.missingConfirmation}
          onChange={(event) =>
            onInsightFiltersChange({
              ...insightFilters,
              missingConfirmation: event.target.value,
            })
          }
        >
          <option value="all">All confirmations</option>
          {insightFilterOptions.missingConfirmation.map((value) => (
            <option key={value} value={value}>
              {readableHeader(value)}
            </option>
          ))}
        </select>
        <select
          aria-label="Risk flag filter"
          value={insightFilters.riskFlag}
          onChange={(event) =>
            onInsightFiltersChange({ ...insightFilters, riskFlag: event.target.value })
          }
        >
          <option value="all">All risks</option>
          {insightFilterOptions.riskFlag.map((value) => (
            <option key={value} value={value}>
              {readableHeader(value)}
            </option>
          ))}
        </select>
        <select
          aria-label="PIT status filter"
          value={insightFilters.pitStatus}
          onChange={(event) =>
            onInsightFiltersChange({ ...insightFilters, pitStatus: event.target.value })
          }
        >
          <option value="all">All PIT</option>
          {insightFilterOptions.pitStatus.map((value) => (
            <option key={value} value={value}>
              {readableHeader(value)}
            </option>
          ))}
        </select>
        <select
          aria-label="Source restriction filter"
          value={insightFilters.sourceRestriction}
          onChange={(event) =>
            onInsightFiltersChange({
              ...insightFilters,
              sourceRestriction: event.target.value,
            })
          }
        >
          <option value="all">All sources</option>
          {insightFilterOptions.sourceRestriction.map((value) => (
            <option key={value} value={value}>
              {readableHeader(value)}
            </option>
          ))}
        </select>
      </div>
      <div className="designer-column-list">
        {allAttributeColumns.slice(0, 12).map((column) => (
          <label key={column}>
            <input
              checked={selectedColumns.includes(column)}
              type="checkbox"
              onChange={() => onSelectedColumnsChange(toggleStringMembership(selectedColumns, column))}
            />
            <span>{readableHeader(column)}</span>
          </label>
        ))}
        <label>
          <input
            checked={showEvidenceColumn}
            type="checkbox"
            onChange={(event) => onShowEvidenceColumnChange(event.target.checked)}
          />
          <span>Evidence count</span>
        </label>
      </div>
      <div className="designer-alert-row">
        <select
          aria-label="Alert type"
          value={alertType}
          onChange={(event) => setAlertType(event.target.value)}
        >
          <option value="score_crosses_threshold">Score threshold</option>
          <option value="rank_enters_top_n">Rank top N</option>
          <option value="event_materiality_above_threshold">Event materiality</option>
          <option value="residual_above_threshold">Residual threshold</option>
          <option value="attribute_missing">Attribute missing</option>
          <option value="relationship_edge_appears">Relationship appears</option>
        </select>
        {alertType === "rank_enters_top_n" ? (
          <input
            aria-label="Alert top N"
            min={1}
            type="number"
            value={alertTopN}
            onChange={(event) => setAlertTopN(Number(event.target.value))}
          />
        ) : (
          <input
            aria-label="Alert threshold"
            step={0.05}
            type="number"
            value={alertThreshold}
            onChange={(event) => setAlertThreshold(Number(event.target.value))}
          />
        )}
      </div>
      <div className="designer-actions">
        <button type="button" disabled={isBusy || !result || !project} onClick={saveRadar}>
          <Save size={13} />
          <span>Radar</span>
        </button>
        <button type="button" disabled={isBusy || !result || !project} onClick={createWatchlist}>
          <BookmarkPlus size={13} />
          <span>Watchlist</span>
        </button>
        <button type="button" disabled={isBusy || !project} onClick={createAlert}>
          <Bell size={13} />
          <span>Alert</span>
        </button>
      </div>
      <div className="designer-schedule-row">
        <select
          aria-label="Radar refresh schedule"
          value={scheduleCadence}
          onChange={(event) =>
            setScheduleCadence(
              event.target.value === "daily" ||
                event.target.value === "weekly" ||
                event.target.value === "on_app_start"
                ? event.target.value
                : "manual",
            )
          }
        >
          <option value="manual">Manual</option>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="on_app_start">On app start</option>
        </select>
        <button type="button" disabled={isBusy || !result || !project} onClick={saveSchedule}>
          <RefreshCw size={13} />
          <span>Schedule</span>
        </button>
      </div>
      <div className="designer-actions">
        <button type="button" disabled={isBusy || !result} onClick={() => exportSurface("csv")}>
          <Download size={13} />
          <span>CSV</span>
        </button>
        <button type="button" disabled={isBusy || !result} onClick={() => exportSurface("json")}>
          <Download size={13} />
          <span>JSON</span>
        </button>
        <button
          type="button"
          disabled={isBusy || !result}
          onClick={() => exportSurface("manifest")}
        >
          <Download size={13} />
          <span>Manifest</span>
        </button>
        <button type="button" disabled={isBusy} onClick={() => exportSurface("methodology")}>
          <Download size={13} />
          <span>Graph</span>
        </button>
      </div>
      {surfaceStatus && <div className="surface-status">{surfaceStatus}</div>}
    </section>
  );
}

function RuntimeJobPanel({
  events,
  job,
  onCancel,
}: {
  events: VizaRuntimeJobEvent[];
  job: VizaRuntimeJobRecord | null;
  onCancel: () => void;
}) {
  if (!job) {
    return (
      <section className="runtime-job-panel">
        <div className="result-label">Runtime</div>
        <div className="result-empty">No runtime job.</div>
      </section>
    );
  }
  const terminal = isTerminalJobStatus(job.status);
  const recentEvents = events.slice(-5);
  return (
    <section className="runtime-job-panel">
      <div className="result-label">Runtime</div>
      <dl className="batch-summary-grid">
        <dt>Status</dt>
        <dd>{readableHeader(job.status)}</dd>
        <dt>Progress</dt>
        <dd>
          {job.progress.current}/{job.progress.total || job.progress.current}
        </dd>
        <dt>Cache</dt>
        <dd>{readableHeader(job.progress.cache_status)}</dd>
        <dt>Result</dt>
        <dd>{job.result_ref ? shortVersionId(job.result_ref) : "-"}</dd>
      </dl>
      <div className="runtime-job-actions">
        <button type="button" disabled={terminal || job.cancel_requested} onClick={onCancel}>
          <CircleStop size={13} />
          <span>Cancel</span>
        </button>
        <span>{job.progress.message}</span>
      </div>
      {recentEvents.length > 0 && (
        <div className="batch-progress-list">
          {recentEvents.map((event) => (
            <span key={event.event_id}>
              {event.sequence}. {readableHeader(event.status)}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

function ProjectVersionPanel({
  diff,
  project,
  versions,
  onCloneVersion,
  onLoadVersion,
  onRevertVersion,
  onSaveVersion,
}: {
  diff: VizaMethodologyVersionDiff | null;
  project: VizaProjectSummary | null;
  versions: VizaMethodologyVersionSummary[];
  onCloneVersion: (version: VizaMethodologyVersionSummary) => void;
  onLoadVersion: (version: VizaMethodologyVersionSummary) => void;
  onRevertVersion: (version: VizaMethodologyVersionSummary) => void;
  onSaveVersion: () => void;
}) {
  const displayedVersions = versions.slice(0, 5);

  return (
    <section className="project-panel">
      <div className="result-label">Project</div>
      <div className="project-panel-header">
        <div>
          <strong>{project?.name ?? "Local project"}</strong>
          <span>{versions.length} saved versions</span>
        </div>
        <button type="button" onClick={onSaveVersion}>
          Save
        </button>
      </div>
      {displayedVersions.length > 0 ? (
        <div className="version-list">
          {displayedVersions.map((version) => (
            <div className="version-row" key={version.version_id}>
              <div>
                <strong>{version.label || version.name}</strong>
                <span>
                  {formatVersionTime(version.created_at)} / {shortHash(version.graph_hash)}
                </span>
                <small>
                  {version.node_count} nodes, {version.edge_count} edges
                </small>
              </div>
              <div className="version-actions">
                <button type="button" onClick={() => onLoadVersion(version)}>
                  Load
                </button>
                <button type="button" onClick={() => onCloneVersion(version)}>
                  Clone
                </button>
                <button type="button" onClick={() => onRevertVersion(version)}>
                  Revert
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="result-empty">No saved versions for this methodology.</div>
      )}
      {diff && (
        <dl className="version-diff-grid">
          <dt>Compare</dt>
          <dd>
            {shortVersionId(diff.left_version_id)} to {shortVersionId(diff.right_version_id)}
          </dd>
          <dt>Nodes</dt>
          <dd>{versionDiffSummary(diff.added_nodes, diff.removed_nodes, diff.changed_nodes)}</dd>
          <dt>Edges</dt>
          <dd>{versionDiffSummary(diff.added_edges, diff.removed_edges, diff.changed_edges)}</dd>
          <dt>Metadata</dt>
          <dd>{diff.metadata_changed ? "changed" : "unchanged"}</dd>
        </dl>
      )}
    </section>
  );
}

function EquityRuntimePreviewPanel() {
  const [status, setStatus] = useState<VizaEquityRuntimeWedgeStatus | null>(null);
  const [isStatusLoaded, setIsStatusLoaded] = useState(false);
  const [cik, setCik] = useState("0000320193");
  const [tickerAlias, setTickerAlias] = useState("AAPL");
  const [packageMode, setPackageMode] = useState<"white_box" | "output_only" | "marketplace_draft">(
    "marketplace_draft",
  );
  const [includeFmp, setIncludeFmp] = useState(false);
  const [includeFred, setIncludeFred] = useState(false);
  const [useLiveConnectors, setUseLiveConnectors] = useState(false);
  const [persistRun, setPersistRun] = useState(false);
  const [preview, setPreview] = useState<VizaEquityRuntimeWedgePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [isRunningPreview, setIsRunningPreview] = useState(false);
  const [recentRuns, setRecentRuns] = useState<VizaEquityPreviewRunSummary[]>([]);
  const [recentRunsTotal, setRecentRunsTotal] = useState(0);
  const [selectedRunDetail, setSelectedRunDetail] = useState<VizaEquityPreviewRunDetail | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingRunDetail, setIsLoadingRunDetail] = useState(false);
  const [isReplayingRun, setIsReplayingRun] = useState(false);
  const [packageDraft, setPackageDraft] = useState<VizaEquityPreviewPackageDraftResponse | null>(null);
  const [packageDraftError, setPackageDraftError] = useState<string | null>(null);
  const [isExportingPackageDraft, setIsExportingPackageDraft] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchEquityRuntimeWedgeStatus()
      .then((payload) => {
        if (!cancelled) {
          setStatus(payload);
          if (!payload.feature_flags.fmp_enabled) {
            setIncludeFmp(false);
          }
          if (!payload.feature_flags.fred_enabled) {
            setIncludeFred(false);
          }
          if (!payload.live_mode_allowed) {
            setUseLiveConnectors(false);
          }
          if (!payload.persistence_enabled) {
            setPersistRun(false);
            setRecentRuns([]);
            setRecentRunsTotal(0);
            setSelectedRunDetail(null);
          }
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatus(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsStatusLoaded(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadRunDetail = useCallback(async (runId: string) => {
    setIsLoadingRunDetail(true);
    setHistoryError(null);
    setPackageDraft(null);
    setPackageDraftError(null);
    try {
      const payload = await fetchEquityPreviewRunDetail(runId);
      setSelectedRunDetail(payload);
    } catch (error) {
      setSelectedRunDetail(null);
      setHistoryError(error instanceof Error ? error.message : "Unable to load persisted preview run.");
    } finally {
      setIsLoadingRunDetail(false);
    }
  }, []);

  const loadHistory = useCallback(
    async (selectRunId?: string | null) => {
      if (!status?.persistence_enabled) {
        setRecentRuns([]);
        setRecentRunsTotal(0);
        return;
      }
      setIsLoadingHistory(true);
      setHistoryError(null);
      try {
        const payload = await fetchEquityPreviewRuns({ limit: 8 });
        setRecentRuns(payload.runs);
        setRecentRunsTotal(payload.total);
        if (selectRunId) {
          await loadRunDetail(selectRunId);
        }
      } catch (error) {
        setHistoryError(error instanceof Error ? error.message : "Unable to load persisted equity preview runs.");
      } finally {
        setIsLoadingHistory(false);
      }
    },
    [loadRunDetail, status?.persistence_enabled],
  );

  useEffect(() => {
    if (status?.persistence_enabled) {
      void loadHistory(null);
    }
  }, [loadHistory, status?.persistence_enabled]);

  const runPreview = useCallback(async () => {
    setIsRunningPreview(true);
    setPreviewError(null);
    try {
      const payload = await previewEquityRuntimeWedge({
        target: {
          cik: cik.trim() || null,
          ticker_alias: tickerAlias.trim() || null,
        },
        profile_id: "quality_value_long_only",
        package_mode: packageMode,
        include_fmp: includeFmp,
        include_fred: includeFred,
        use_live_connectors: useLiveConnectors,
        cutoff_timestamp: null,
        mock_fixture_id: status?.mock_fixture_id ?? "sec_fmp_fred_runtime_wedge_fixture",
        persist_run: persistRun,
      });
      setPreview(payload);
      if (payload.persisted && payload.run_id) {
        await loadHistory(payload.run_id);
      }
    } catch (error) {
      setPreview(null);
      setPreviewError(error instanceof Error ? error.message : "Preview failed.");
    } finally {
      setIsRunningPreview(false);
    }
  }, [
    cik,
    includeFmp,
    includeFred,
    loadHistory,
    packageMode,
    persistRun,
    status?.mock_fixture_id,
    tickerAlias,
    useLiveConnectors,
  ]);

  const replayStoredRun = useCallback(
    async (runId: string, mode: "replay_from_stored_observations" | "replay_with_refresh") => {
      setIsReplayingRun(true);
      setHistoryError(null);
      try {
        const payload = await replayEquityPreviewRun(runId, {
          mode,
          package_mode: packageMode,
          include_fmp: includeFmp,
          include_fred: includeFred,
        });
        setPreview(payload.preview);
        await loadHistory(payload.run_id);
      } catch (error) {
        setHistoryError(error instanceof Error ? error.message : "Replay failed.");
      } finally {
        setIsReplayingRun(false);
      }
    },
    [includeFmp, includeFred, loadHistory, packageMode],
  );

  const exportSelectedPackageDraft = useCallback(
    async (runId: string) => {
      setIsExportingPackageDraft(true);
      setPackageDraftError(null);
      try {
        const payload = await exportEquityPreviewPackageDraft(runId, {
          package_mode: packageMode,
          not_investment_advice_acknowledged: true,
        });
        setPackageDraft(payload);
      } catch (error) {
        setPackageDraft(null);
        setPackageDraftError(error instanceof Error ? error.message : "Package draft export failed.");
      } finally {
        setIsExportingPackageDraft(false);
      }
    },
    [packageMode],
  );

  if (!isStatusLoaded || !status?.enabled) {
    return null;
  }

  const packageModes = status.package_modes.length ? status.package_modes : ["white_box", "output_only", "marketplace_draft"];

  return (
    <section className="equity-preview-panel">
      <div className="panel-heading-row">
        <div>
          <div className="result-label">Equity Runtime Wedge Preview</div>
          <p className="panel-subcopy">Feature-flagged research preview using the packaged local engine.</p>
        </div>
        <EquityPreviewStatusPill status={preview?.profile.compatibility_status ?? "warn"} />
      </div>
      <div className="equity-preview-controls">
        <label>
          <span>CIK</span>
          <input value={cik} onChange={(event) => setCik(event.target.value)} />
        </label>
        <label>
          <span>Ticker alias</span>
          <input value={tickerAlias} onChange={(event) => setTickerAlias(event.target.value.toUpperCase())} />
        </label>
        <label>
          <span>Profile</span>
          <select value="quality_value_long_only" disabled>
            <option value="quality_value_long_only">quality_value_long_only</option>
          </select>
        </label>
        <label>
          <span>Package mode</span>
          <select
            value={packageMode}
            onChange={(event) =>
              setPackageMode(event.target.value as "white_box" | "output_only" | "marketplace_draft")
            }
          >
            {packageModes.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-toggle">
          <input
            checked={includeFmp}
            disabled={!status.feature_flags.fmp_enabled}
            type="checkbox"
            onChange={(event) => setIncludeFmp(event.target.checked)}
          />
          <span>Include FMP</span>
        </label>
        <label className="inline-toggle">
          <input
            checked={includeFred}
            disabled={!status.feature_flags.fred_enabled}
            type="checkbox"
            onChange={(event) => setIncludeFred(event.target.checked)}
          />
          <span>Include FRED</span>
        </label>
        <label className="inline-toggle">
          <input
            checked={useLiveConnectors}
            disabled={!status.live_mode_allowed}
            type="checkbox"
            onChange={(event) => setUseLiveConnectors(event.target.checked)}
          />
          <span>Live connectors</span>
        </label>
        <label className="inline-toggle">
          <input
            checked={persistRun}
            disabled={!status.persistence_enabled}
            type="checkbox"
            onChange={(event) => setPersistRun(event.target.checked)}
          />
          <span>Save run</span>
        </label>
        <button className="secondary-button" disabled={isRunningPreview} onClick={runPreview}>
          {isRunningPreview ? "Running..." : "Run Preview"}
        </button>
      </div>
      {previewError && <div className="result-empty">{previewError}</div>}
      {preview && (
        <div className="equity-preview-output">
          <EquityPreviewSection title="Target / identity">
            <dl className="payload-grid">
              <dt>Name</dt>
              <dd>{preview.target.display_name || "-"}</dd>
              <dt>CIK</dt>
              <dd>{preview.target.cik || "-"}</dd>
              <dt>Ticker alias</dt>
              <dd>{preview.target.ticker_alias || "-"}</dd>
              <dt>Entity ID</dt>
              <dd>{preview.target.entity_id || "-"}</dd>
            </dl>
            <p className="panel-subcopy">{preview.target.primary_key_policy}</p>
          </EquityPreviewSection>
          <EquityPreviewSection title="Profile compatibility">
            <EquityPreviewStatusPill status={preview.profile.compatibility_status} />
            <EquityPreviewMessageList items={[...preview.profile.blocks, ...preview.profile.warnings]} />
          </EquityPreviewSection>
          <EquityPreviewSection title="Evidence summary">
            <dl className="payload-grid">
              <dt>Sources</dt>
              <dd>{preview.evidence_summary.source_count}</dd>
              <dt>Observed</dt>
              <dd>{preview.evidence_summary.observed_at || "-"}</dd>
              <dt>Available</dt>
              <dd>{preview.evidence_summary.available_at || "-"}</dd>
              <dt>Retrieved</dt>
              <dd>{preview.evidence_summary.retrieved_at || "-"}</dd>
            </dl>
            <EquityPreviewMessageList items={preview.evidence_summary.filing_refs} />
          </EquityPreviewSection>
          <EquityPreviewSection title="Fundamental attributes">
            <div className="equity-preview-table-wrap">
              <table className="compact-table">
                <thead>
                  <tr>
                    <th>Attribute</th>
                    <th>Value</th>
                    <th>PIT</th>
                    <th>Rights</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.fundamental_attributes.slice(0, 8).map((attribute) => (
                    <tr key={String(attribute.key)}>
                      <td>{readableHeader(String(attribute.key ?? ""))}</td>
                      <td>{formatPreviewValue(attribute.value)}</td>
                      <td>{String(attribute.pit_status ?? "-")}</td>
                      <td>{String(attribute.rights_status ?? "-")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </EquityPreviewSection>
          <EquityPreviewSection title="Optional context">
            <dl className="payload-grid">
              <dt>FMP</dt>
              <dd>{`${preview.optional_market_context.fmp.status} / ${preview.optional_market_context.fmp.rights_status}`}</dd>
              <dt>FRED</dt>
              <dd>{`${preview.optional_market_context.fred.status} / ${preview.optional_market_context.fred.pit_status}`}</dd>
            </dl>
            <EquityPreviewMessageList
              items={[
                ...(preview.optional_market_context.fmp.warnings ?? []),
                ...(preview.optional_market_context.fred.warnings ?? []),
              ]}
            />
          </EquityPreviewSection>
          <EquityPreviewSection title="Output preview">
            <p className="panel-subcopy">{preview.output_preview.non_advice_boundary}</p>
            <EquityPreviewMessageList items={preview.output_preview.summary_cards} />
            <EquityPreviewMessageList items={preview.output_preview.missing_data_warnings} />
          </EquityPreviewSection>
          <EquityPreviewSection title="Validation report">
            <EquityPreviewStatusPill status={preview.validation_report.status} />
            <EquityPreviewMessageList items={preview.validation_report.rules} />
          </EquityPreviewSection>
          <EquityPreviewSection title="Source-rights report">
            <EquityPreviewStatusPill status={preview.source_rights_report.status} />
            <EquityPreviewMessageList items={preview.source_rights_report.policies} />
          </EquityPreviewSection>
          <EquityPreviewSection title="Package redaction preview">
            <dl className="payload-grid">
              <dt>Mode</dt>
              <dd>{preview.package_redaction_preview.package_mode}</dd>
              <dt>Included</dt>
              <dd>{preview.package_redaction_preview.included.length}</dd>
              <dt>Redacted</dt>
              <dd>{preview.package_redaction_preview.redacted.length}</dd>
              <dt>Blocked</dt>
              <dd>{preview.package_redaction_preview.blocked.length}</dd>
            </dl>
            <EquityPreviewMessageList
              items={[
                ...preview.package_redaction_preview.redacted,
                ...preview.package_redaction_preview.blocked,
                ...preview.package_redaction_preview.entitlement_locked,
              ]}
            />
          </EquityPreviewSection>
          <EquityPreviewSection title="Audit">
            <dl className="payload-grid">
              <dt>Run ID</dt>
              <dd>{preview.audit.run_id}</dd>
              <dt>Fixture</dt>
              <dd>{preview.audit.fixture_mode ? "mock" : "live opt-in"}</dd>
              <dt>Proof</dt>
              <dd>{preview.audit.proof_checksum.slice(0, 16)}</dd>
              <dt>Persistence</dt>
              <dd>{preview.persistence_status ?? "skipped"}</dd>
            </dl>
          </EquityPreviewSection>
        </div>
      )}
      <EquityPreviewRunHistory
        historyError={historyError}
        isLoadingHistory={isLoadingHistory}
        isLoadingRunDetail={isLoadingRunDetail}
        isReplayingRun={isReplayingRun}
        onLoadHistory={() => void loadHistory(null)}
        onLoadRunDetail={loadRunDetail}
        onPackageDraft={exportSelectedPackageDraft}
        onReplayRun={replayStoredRun}
        packageDraft={packageDraft}
        packageDraftError={packageDraftError}
        recentRuns={recentRuns}
        recentRunsTotal={recentRunsTotal}
        replayRefreshEnabled={status.replay_refresh_enabled}
        selectedRunDetail={selectedRunDetail}
        isExportingPackageDraft={isExportingPackageDraft}
        visible={status.persistence_enabled}
      />
    </section>
  );
}

function EquityPreviewSection({ children, title }: { children: ReactNode; title: string }) {
  return (
    <div className="equity-preview-section">
      <div className="section-kicker">{title}</div>
      {children}
    </div>
  );
}

function EquityPreviewRunHistory({
  historyError,
  isLoadingHistory,
  isLoadingRunDetail,
  isExportingPackageDraft,
  isReplayingRun,
  onLoadHistory,
  onLoadRunDetail,
  onPackageDraft,
  onReplayRun,
  packageDraft,
  packageDraftError,
  recentRuns,
  recentRunsTotal,
  replayRefreshEnabled,
  selectedRunDetail,
  visible,
}: {
  historyError: string | null;
  isLoadingHistory: boolean;
  isLoadingRunDetail: boolean;
  isExportingPackageDraft: boolean;
  isReplayingRun: boolean;
  onLoadHistory: () => void;
  onLoadRunDetail: (runId: string) => void;
  onPackageDraft: (runId: string) => void;
  onReplayRun: (runId: string, mode: "replay_from_stored_observations" | "replay_with_refresh") => void;
  packageDraft: VizaEquityPreviewPackageDraftResponse | null;
  packageDraftError: string | null;
  recentRuns: VizaEquityPreviewRunSummary[];
  recentRunsTotal: number;
  replayRefreshEnabled: boolean;
  selectedRunDetail: VizaEquityPreviewRunDetail | null;
  visible: boolean;
}) {
  if (!visible) {
    return null;
  }

  const selectedRunId = readString(selectedRunDetail?.run_record?.run_id);
  const selectedRunInput = (selectedRunDetail?.run_record?.input ?? {}) as Record<string, unknown>;
  const selectedRunConnectorModes = (selectedRunDetail?.run_record?.connector_modes ?? {}) as Record<string, unknown>;
  const selectedRunFlags = (selectedRunDetail?.run_record?.feature_flags ?? {}) as Record<string, unknown>;
  const selectedOutput = selectedRunDetail?.output_preview as Record<string, unknown> | undefined;

  return (
    <div className="equity-preview-history">
      <div className="panel-heading-row">
        <div>
          <div className="result-label">Recent Equity Preview Runs</div>
          <p className="panel-subcopy">
            Persisted audit history for replayable research previews. Ticker stays an alias; CIK and internal IDs anchor the run.
          </p>
        </div>
        <button className="secondary-button" disabled={isLoadingHistory} onClick={onLoadHistory}>
          {isLoadingHistory ? "Refreshing..." : "Refresh"}
        </button>
      </div>
      {historyError && <div className="result-empty">{historyError}</div>}
      <div className="equity-preview-table-wrap">
        <table className="compact-table">
          <thead>
            <tr>
              <th>Target</th>
              <th>Status</th>
              <th>PIT</th>
              <th>Rights</th>
              <th>Validation</th>
              <th>Proof</th>
            </tr>
          </thead>
          <tbody>
            {recentRuns.map((run) => (
              <tr key={run.run_id}>
                <td>
                  <button className="link-button" onClick={() => onLoadRunDetail(run.run_id)}>
                    {run.target_display_name || run.cik || run.ticker_alias || shortHash(run.run_id)}
                  </button>
                  <div className="muted-inline">
                    {run.cik || "-"} / {run.ticker_alias || "-"} / {run.package_mode}
                  </div>
                </td>
                <td>
                  <EquityPreviewStatusPill status={run.status} />
                </td>
                <td>{run.pit_status}</td>
                <td>{run.rights_status}</td>
                <td>{run.validation_status}</td>
                <td>{shortHash(run.proof_checksum)}</td>
              </tr>
            ))}
            {!recentRuns.length && (
              <tr>
                <td colSpan={6}>No persisted preview runs yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="panel-subcopy">Showing {recentRuns.length} of {recentRunsTotal} saved runs.</p>
      {isLoadingRunDetail && <div className="result-empty">Loading run detail...</div>}
      {selectedRunDetail && (
        <div className="equity-preview-output">
          <EquityPreviewSection title="Run detail">
            <dl className="payload-grid">
              <dt>Run ID</dt>
              <dd>{selectedRunId}</dd>
              <dt>Parent run</dt>
              <dd>{readString(selectedRunDetail.run_record.parent_run_id, "-")}</dd>
              <dt>Created from</dt>
              <dd>{readString(selectedRunDetail.run_record.created_from, "-")}</dd>
              <dt>Proof</dt>
              <dd>{shortHash(readString(selectedRunDetail.audit.proof_checksum))}</dd>
            </dl>
          </EquityPreviewSection>
          <EquityPreviewSection title="Target / input">
            <dl className="payload-grid">
              <dt>Name</dt>
              <dd>{readString(selectedRunDetail.target.display_name, "-")}</dd>
              <dt>Entity ID</dt>
              <dd>{readString(selectedRunDetail.target.entity_id, "-")}</dd>
              <dt>CIK</dt>
              <dd>{readString(selectedRunDetail.target.cik, "-")}</dd>
              <dt>Ticker alias</dt>
              <dd>{readString(selectedRunDetail.target.ticker_alias, "-")}</dd>
              <dt>Package mode</dt>
              <dd>{readString(selectedRunInput.package_mode, "-")}</dd>
            </dl>
            <p className="panel-subcopy">Ticker is display/lookup alias only, not a persisted primary key.</p>
          </EquityPreviewSection>
          <EquityPreviewSection title="Connector modes / flags">
            <dl className="payload-grid">
              <dt>SEC</dt>
              <dd>{readString(selectedRunConnectorModes.sec, "-")}</dd>
              <dt>FMP</dt>
              <dd>{readString(selectedRunConnectorModes.fmp, "-")}</dd>
              <dt>FRED</dt>
              <dd>{readString(selectedRunConnectorModes.fred, "-")}</dd>
              <dt>Persistence</dt>
              <dd>{formatPreviewValue(selectedRunFlags.preview_persistence_enabled)}</dd>
            </dl>
          </EquityPreviewSection>
          <EquityPreviewSection title="Stored evidence / observations">
            <dl className="payload-grid">
              <dt>Sources</dt>
              <dd>{readArray(selectedRunDetail.evidence_bundle.source_refs).length}</dd>
              <dt>Filings</dt>
              <dd>{readArray(selectedRunDetail.evidence_bundle.filing_refs).length}</dd>
              <dt>Observations</dt>
              <dd>{selectedRunDetail.observations.length}</dd>
              <dt>Attributes</dt>
              <dd>{readArray(selectedRunDetail.evidence_bundle.fundamental_attribute_keys).length}</dd>
            </dl>
            <EquityPreviewMessageList items={selectedRunDetail.observations.slice(0, 6)} />
          </EquityPreviewSection>
          <EquityPreviewSection title="Validation / rights / redaction">
            <dl className="payload-grid">
              <dt>Validation</dt>
              <dd>{readString(selectedRunDetail.validation_report.status, "-")}</dd>
              <dt>Rights</dt>
              <dd>{readString(selectedRunDetail.source_rights_report.status, "-")}</dd>
              <dt>Package</dt>
              <dd>{readString(selectedRunDetail.package_redaction_preview.package_mode, "-")}</dd>
              <dt>Redacted</dt>
              <dd>{selectedRunDetail.package_redaction_preview.redacted?.length ?? 0}</dd>
            </dl>
            <EquityPreviewMessageList
              items={[
                ...(selectedRunDetail.package_redaction_preview.redacted ?? []),
                ...(selectedRunDetail.package_redaction_preview.blocked ?? []),
                ...(selectedRunDetail.package_redaction_preview.entitlement_locked ?? []),
              ]}
            />
          </EquityPreviewSection>
          <EquityPreviewSection title="Package preview / export draft">
            <p className="panel-subcopy">
              Builds a local .viza draft from the persisted run with PIT, rights, validation, proof, and redaction sections.
            </p>
            <div className="equity-preview-actions">
              <button
                className="secondary-button"
                disabled={isExportingPackageDraft}
                onClick={() => onPackageDraft(selectedRunId)}
              >
                {isExportingPackageDraft ? "Preparing..." : "Prepare .viza draft package"}
              </button>
            </div>
            {packageDraftError && <div className="result-empty">{packageDraftError}</div>}
            {packageDraft && (
              <dl className="payload-grid">
                <dt>Status</dt>
                <dd>{packageDraft.package_ready_status}</dd>
                <dt>Mode</dt>
                <dd>{packageDraft.package_mode}</dd>
                <dt>Path</dt>
                <dd>{packageDraft.target_path}</dd>
                <dt>Proof</dt>
                <dd>{shortHash(packageDraft.proof_checksum)}</dd>
              </dl>
            )}
            {packageDraft && <EquityPreviewMessageList items={packageDraft.warnings} />}
          </EquityPreviewSection>
          <EquityPreviewSection title="Replay">
            <p className="panel-subcopy">
              {readString(selectedOutput?.non_advice_boundary, "Research preview only; not investment advice.")}
            </p>
            <div className="equity-preview-actions">
              <button
                className="secondary-button"
                disabled={isReplayingRun}
                onClick={() => onReplayRun(selectedRunId, "replay_from_stored_observations")}
              >
                {isReplayingRun ? "Replaying..." : "Replay from stored observations"}
              </button>
              <button
                className="secondary-button"
                disabled={isReplayingRun || !replayRefreshEnabled}
                onClick={() => onReplayRun(selectedRunId, "replay_with_refresh")}
              >
                Replay with refresh
              </button>
            </div>
            {!replayRefreshEnabled && (
              <p className="panel-subcopy">Refresh replay is disabled until the replay refresh flag is enabled.</p>
            )}
          </EquityPreviewSection>
        </div>
      )}
    </div>
  );
}

function EquityPreviewStatusPill({ status }: { status: string }) {
  return <span className={`equity-status-pill ${status}`}>{status}</span>;
}

type EquityPreviewMessageItem = string | object;

function EquityPreviewMessageList({ items }: { items: EquityPreviewMessageItem[] }) {
  if (!items.length) {
    return <div className="result-empty">No issues.</div>;
  }
  return (
    <ul className="equity-preview-list">
      {items.slice(0, 8).map((item, index) => (
        <li key={equityPreviewListKey(item, index)}>{equityPreviewMessage(item)}</li>
      ))}
    </ul>
  );
}

function equityPreviewListKey(item: EquityPreviewMessageItem, index: number): string {
  if (typeof item === "string") {
    return `${item}-${index}`;
  }
  const row = item as Record<string, unknown>;
  return String(row.rule_id ?? row.code ?? row.source_id ?? row.source ?? row.title ?? index);
}

function equityPreviewMessage(item: EquityPreviewMessageItem): string {
  if (typeof item === "string") {
    return item;
  }
  const row = item as Record<string, unknown>;
  const title = row.title ?? row.rule_id ?? row.code ?? row.source ?? row.accession_number ?? "detail";
  const body = row.message ?? row.reason ?? row.body ?? row.form_type ?? row.license_policy ?? "";
  const status = row.status ? ` [${String(row.status)}]` : "";
  return `${String(title)}${status}${body ? `: ${String(body)}` : ""}`;
}

function readArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function formatPreviewValue(value: unknown): string {
  if (
    typeof value === "number" ||
    typeof value === "string" ||
    typeof value === "boolean" ||
    value === null ||
    typeof value === "undefined"
  ) {
    return formatCell(value);
  }
  return JSON.stringify(value);
}

function DiagnosticsPanel({
  desktopStatus,
  diagnostics,
  engineStatus,
  isRestartingEngine,
  onRefresh,
  onRestart,
}: {
  desktopStatus: VizaDesktopStatus | null;
  diagnostics: VizaRuntimeDiagnostics | null;
  engineStatus: EngineStatus;
  isRestartingEngine: boolean;
  onRefresh: () => void;
  onRestart: () => void;
}) {
  const projectStore = diagnostics?.project_store ?? null;
  const canRestart = Boolean(window.vizaDesktop?.restartEngine);

  return (
    <section className="diagnostics-panel">
      <div className="diagnostics-header">
        <div className="result-label">Diagnostics</div>
        <div className="diagnostics-actions">
          <button
            className="icon-button compact"
            type="button"
            title="Export diagnostics bundle"
            onClick={() => exportDiagnosticsBundle(diagnostics, desktopStatus)}
          >
            <Download size={15} />
          </button>
          <button
            className="icon-button compact"
            type="button"
            title="Refresh diagnostics"
            onClick={onRefresh}
          >
            <RefreshCw size={15} />
          </button>
          {canRestart && (
            <button
              className="icon-button compact"
              type="button"
              title="Restart local engine"
              disabled={isRestartingEngine}
              onClick={onRestart}
            >
              <RotateCcw size={15} />
            </button>
          )}
        </div>
      </div>
      <dl className="diagnostics-grid">
        <dt>Engine</dt>
        <dd>{diagnostics ? `${diagnostics.engine_version} (${diagnostics.status})` : engineStatus}</dd>
        <dt>Python</dt>
        <dd>{diagnostics?.python_version ?? "-"}</dd>
        <dt>Desktop</dt>
        <dd>{desktopStatus ? `${desktopStatus.appVersion} ${desktopStatus.isPackaged ? "packaged" : "dev"}` : "-"}</dd>
        <dt>Mode</dt>
        <dd>{desktopStatus?.engineRuntimeMode ?? "-"}</dd>
        <dt>Runtime</dt>
        <dd title={desktopStatus?.engineRoot ?? diagnostics?.package_root ?? ""}>
          {desktopStatus?.engineRoot ?? diagnostics?.package_root ?? "-"}
        </dd>
        <dt>Config</dt>
        <dd title={diagnostics?.config_root ?? ""}>{summarizeConfigFiles(diagnostics)}</dd>
        <dt>Project</dt>
        <dd title={projectStore?.path ?? ""}>{projectStore?.path ?? "-"}</dd>
        <dt>Log</dt>
        <dd title={desktopStatus?.engineLogPath ?? ""}>{desktopStatus?.engineLogPath || "-"}</dd>
        <dt>Connectors</dt>
        <dd>{summarizeDiagnosticConnectors(diagnostics)}</dd>
        <dt>Credential mode</dt>
        <dd>{diagnostics?.credential_mode ?? "-"}</dd>
        <dt>File format</dt>
        <dd>{diagnostics?.file_format_version ?? "-"}</dd>
        <dt>Modules</dt>
        <dd>{summarizeInstalledModules(diagnostics)}</dd>
        <dt>Observations</dt>
        <dd>{summarizeObservationHealth(diagnostics)}</dd>
        <dt>.viza files</dt>
        <dd>{summarizeFileHealth(diagnostics)}</dd>
        <dt>Quarantine</dt>
        <dd>{summarizeQuarantine(diagnostics)}</dd>
        <dt>Updates</dt>
        <dd>manual</dd>
        <dt>Last run</dt>
        <dd>{formatLastRun(projectStore)}</dd>
      </dl>
      {diagnostics?.checks.length ? (
        <div className="diagnostic-check-list">
          {diagnostics.checks.map((check) => (
            <div className="diagnostic-check-row" key={check.name}>
              <span className={`connector-status ${diagnosticStatusClass(check.status)}`}>
                {readableHeader(check.status)}
              </span>
              <div>
                <strong>{readableHeader(check.name)}</strong>
                <span>{check.message}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="result-empty">Diagnostics unavailable.</div>
      )}
    </section>
  );
}

function ConnectorPanel({
  connectors,
  manifest,
}: {
  connectors: VizaConnectorDefinition[];
  manifest: Record<string, unknown>;
}) {
  const manifestConnectors = isRecord(manifest.connectors) ? manifest.connectors : {};
  const connectorRows = connectors.slice(0, 8);

  return (
    <section className="connector-panel">
      <div className="result-label">Connectors</div>
      {connectorRows.length > 0 ? (
        <div className="connector-list">
          {connectorRows.map((connector) => {
            const rawManifestEntry = manifestConnectors[connector.connector_id];
            const manifestEntry: Record<string, unknown> | null = isRecord(rawManifestEntry)
              ? rawManifestEntry
              : null;
            const attributeKeys = manifestEntry
              ? readStringArray(manifestEntry["attribute_keys"])
              : [];
            return (
              <div className="connector-row" key={connector.connector_id}>
                <div>
                  <strong>{connector.display_name}</strong>
                  <span>{readableHeader(connector.source_type)}</span>
                </div>
                <span className={`connector-status ${connectorStatusClass(connector.status)}`}>
                  {readableHeader(connector.status)}
                </span>
                {attributeKeys.length > 0 && (
                  <small>{attributeKeys.slice(0, 3).join(", ")}</small>
                )}
                {connector.credential_requirements.some((credential) => credential.required) && (
                  <small>
                    {connector.credential_requirements
                      .map((credential) =>
                        credential.configured
                          ? `${credential.display_name}: configured`
                          : `${credential.display_name}: needed`,
                      )
                      .join("; ")}
                  </small>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="result-empty">No connector metadata loaded.</div>
      )}
    </section>
  );
}

function AuditPanel({ result }: { result: MethodologyRunResult | null }) {
  const manifest = isRecord(result?.manifest) ? result.manifest : {};
  const dataVersions = readStringArray(manifest["data_versions"]);
  const modelVersions = readStringArray(manifest["model_versions"]);
  const connectorStates = isRecord(manifest["connector_states"])
    ? manifest["connector_states"]
    : {};

  return (
    <section className="audit-panel">
      <div className="result-label">Audit</div>
      {result ? (
        <dl className="audit-grid">
          <dt>Run</dt>
          <dd>{result.run_id}</dd>
          <dt>Graph</dt>
          <dd>{shortHash(result.graph_hash)}</dd>
          <dt>Result</dt>
          <dd>{shortHash(result.result_checksum)}</dd>
          <dt>Evidence</dt>
          <dd>{shortHash(readString(manifest["evidence_checksum"]))}</dd>
          <dt>Started</dt>
          <dd>{formatVersionTime(readString(manifest["run_started_at"]))}</dd>
          <dt>Data</dt>
          <dd>{dataVersions.length ? dataVersions.join(", ") : "none"}</dd>
          <dt>Models</dt>
          <dd>{modelVersions.length ? modelVersions.join(", ") : "none"}</dd>
          <dt>Sources</dt>
          <dd>{Object.entries(connectorStates).map(([key, value]) => `${key}:${value}`).join(", ")}</dd>
        </dl>
      ) : (
        <div className="result-empty">Run a methodology to create an audit manifest.</div>
      )}
    </section>
  );
}

function ValidationPanel({ result }: { result: MethodologyRunResult | null }) {
  const [record, setRecord] = useState<VizaValidationRecord | null>(null);
  const [status, setStatus] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const manifest = isRecord(result?.manifest) ? result.manifest : {};
  const evidenceChecksum = readString(manifest["evidence_checksum"]);
  const proofStatus = validationProofStatus(result, record, evidenceChecksum);

  useEffect(() => {
    setRecord(null);
    setStatus("");
  }, [result?.run_id]);

  const recordValidation = async () => {
    if (!result) {
      setStatus("Run a methodology first.");
      return;
    }
    setIsBusy(true);
    try {
      const saved = await createVizaValidationRecord(result);
      setRecord(saved);
      setStatus(`Recorded ${shortHash(saved.validation_record_id)}.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Validation recording failed.");
    } finally {
      setIsBusy(false);
    }
  };

  const exportProof = () => {
    if (!record) {
      setStatus("Record validation first.");
      return;
    }
    const proof = {
      schema: record.schema,
      validation_record_id: record.validation_record_id,
      run_id: record.run_id,
      graph_hash: record.graph_hash,
      result_checksum: record.result_checksum,
      evidence_checksum: record.evidence_checksum,
      PIT_summary: record.PIT_summary,
      data_versions: record.data_versions,
      model_versions: record.model_versions,
      connector_states: record.connector_states,
      output_references: record.outputs,
      warnings: record.warnings,
      performance_observation: record.performance_observation,
      not_performance_claim: record.performance_observation.status === "pending",
    };
    downloadText("validation-proof.viza.json", JSON.stringify(proof, null, 2) + "\n", "application/json");
    setStatus("Exported validation proof.");
  };

  return (
    <section className="validation-panel">
      <div className="result-label">Validation</div>
      {result ? (
        <>
          <dl className="audit-grid">
            <dt>Status</dt>
            <dd>{proofStatus}</dd>
            <dt>Record</dt>
            <dd>{record ? shortHash(record.validation_record_id) : "not recorded"}</dd>
            <dt>Observation</dt>
            <dd>{record ? readString(record.performance_observation.status, "pending") : "pending"}</dd>
            <dt>Replay</dt>
            <dd>{evidenceChecksum ? "replayable" : "missing source data"}</dd>
          </dl>
          <div className="designer-actions validation-actions">
            <button type="button" disabled={isBusy || !evidenceChecksum} onClick={recordValidation}>
              <Save size={13} />
              <span>Record</span>
            </button>
            <button type="button" disabled={!record} onClick={exportProof}>
              <Download size={13} />
              <span>Proof</span>
            </button>
          </div>
          {status && <div className="surface-status">{status}</div>}
        </>
      ) : (
        <div className="result-empty">Run a methodology to record validation.</div>
      )}
    </section>
  );
}

function EvidenceInspector({
  evidence,
  evidenceRef,
  relationships,
}: {
  evidence: Record<string, unknown>;
  evidenceRef: string | null;
  relationships: VizaRelationshipEdge[];
}) {
  const evidenceDetail = evidenceRef ? evidence[evidenceRef] : null;
  const evidenceRecord = isRecord(evidenceDetail) ? evidenceDetail : null;
  const relationship = relationships.find(
    (edge) =>
      edge.evidence_ref === evidenceRef ||
      edge.target === evidenceRef ||
      edge.source === evidenceRef,
  );

  return (
    <section className="evidence-panel">
      <div className="result-label">Evidence</div>
      {evidenceRef ? <strong>{evidenceRef}</strong> : <span className="result-empty">None</span>}
      {evidenceRecord && (
        <AttributeSourceBadge
          exportAllowed={readExportAllowed(evidenceRecord)}
          isPrototype={readBoolean(evidenceRecord.is_prototype, false)}
          observationId={readString(evidenceRecord.observation_id)}
          source={readString(evidenceRecord.source)}
        />
      )}
      {relationship && (
        <dl className="evidence-grid">
          <dt>Edge</dt>
          <dd>{readableHeader(relationship.relationship_type)}</dd>
          <dt>Source</dt>
          <dd>{relationship.source}</dd>
          <dt>Target</dt>
          <dd>{relationship.target}</dd>
          <dt>Weight</dt>
          <dd>{formatCell(relationship.weight)}</dd>
          <dt>Family</dt>
          <dd>{readableHeader(relationship.family || relationship.relationship_family)}</dd>
          <dt>Objects</dt>
          <dd>
            {[relationship.source_type, relationship.target_type].filter(Boolean).join(" -> ")}
          </dd>
          <dt>Confidence</dt>
          <dd>{formatCell(relationship.confidence)}</dd>
        </dl>
      )}
      {evidenceRecord && (
        <dl className="evidence-grid">
          {Object.entries(evidenceRecord).map(([key, value]) => (
            <Fragment key={key}>
              <dt>{readableHeader(key)}</dt>
              <dd>{formatEvidenceValue(value)}</dd>
            </Fragment>
          ))}
        </dl>
      )}
    </section>
  );
}

function buildRelationshipGraphNodes(
  row: VizaRadarRow,
  edges: VizaRelationshipEdge[],
  centerRefs: Set<string>,
): RelationshipGraphNode[] {
  const companyRef = `company:${row.ticker}`;
  const centerRef = row.entity_id ?? companyRef;
  const nodes: RelationshipGraphNode[] = [
    {
      id: centerRef,
      label: row.ticker,
      kind: "entity",
      x: 76,
      y: 110,
      evidenceRef: centerRef,
    },
  ];
  const seen = new Set(centerRefs);
  seen.add(centerRef);
  const targets = edges
    .map((edge) => (centerRefs.has(edge.source) ? edge.target : edge.source))
    .filter((id) => !seen.has(id))
    .slice(0, 14);
  const radius = 82;
  const centerX = 330;
  const centerY = 110;

  targets.forEach((id, index) => {
    seen.add(id);
    const angle = targets.length === 1 ? 0 : (-120 + (240 * index) / (targets.length - 1));
    const radians = (angle * Math.PI) / 180;
    const edge = edges.find((item) => item.source === id || item.target === id);
    nodes.push({
      id,
      label: id.split(":").slice(1).join(":") || id,
      kind: relationshipNodeKind(id, edge?.relationship_type),
      x: Math.round(centerX + Math.cos(radians) * radius),
      y: Math.round(centerY + Math.sin(radians) * radius),
      evidenceRef: edge?.evidence_ref ?? id,
    });
  });

  return nodes;
}

function relationshipNodeKind(
  id: string,
  relationshipType: string | undefined,
): RelationshipGraphNodeKind {
  if (id.startsWith("insight:")) {
    return "insight";
  }
  if (id.startsWith("asset:")) {
    return "asset";
  }
  if (id.startsWith("strategy_profile:") || id.startsWith("strategy-profile:")) {
    return "strategy_profile";
  }
  if (id.startsWith("output:")) {
    return "output";
  }
  if (id.startsWith("attribute:") || id.startsWith("attr:") || id.startsWith("evidence:attr:")) {
    return "attribute";
  }
  if (id.startsWith("sector:")) {
    return "sector";
  }
  if (id.startsWith("industry:")) {
    return "industry";
  }
  if (id.startsWith("event:")) {
    return "event";
  }
  if (relationshipType === "peer") {
    return "peer";
  }
  if (id.startsWith("company:") || id.startsWith("entity-")) {
    return "entity";
  }
  return "attribute";
}

function edgeLabel(edge: VizaRelationshipEdge): string {
  const label = edge.relationship_type || edge.family || edge.relationship_family;
  if (label === "derived_from") {
    return "derived";
  }
  if (label === "depends_on") {
    return "depends";
  }
  return readableHeader(label).split(" ").slice(0, 2).join(" ");
}

function validationProofStatus(
  result: MethodologyRunResult | null,
  record: VizaValidationRecord | null,
  evidenceChecksum: string,
): string {
  if (!result) {
    return "not replayable";
  }
  if (!evidenceChecksum) {
    return "missing source data";
  }
  if (!record) {
    return "replayable";
  }
  const observationStatus = readString(record.performance_observation.status, "pending");
  return observationStatus === "pending" ? "pending observation" : "recorded";
}

function relationshipTargetLabel(edge: VizaRelationshipEdge, evidenceDetail: unknown): string {
  if (isRecord(evidenceDetail)) {
    const value = evidenceDetail.value;
    if (typeof value === "string" && value) {
      return value;
    }
    const attributeKey = evidenceDetail.attribute_key;
    if (typeof attributeKey === "string" && attributeKey) {
      return readableHeader(attributeKey);
    }
  }
  return edge.target.split(":").slice(1).join(":") || edge.target;
}

function shortGraphLabel(label: string): string {
  return label.length > 14 ? `${label.slice(0, 12)}..` : label;
}

function graphNodeToFlowNode(node: VizaGraphNode): VizaFlowNode {
  const definition = NODE_DEFINITIONS[node.type];
  return {
    id: node.id,
    type: "vizaNode",
    position: node.position,
    data: {
      vizaType: node.type,
      label: node.label ?? definition.label,
      moduleId: definition.moduleId,
      moduleType: definition.moduleType,
      config: node.config,
    },
  };
}

function graphEdgeToFlowEdge(edge: VizaGraphEdge): VizaFlowEdge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    markerEnd: { type: MarkerType.ArrowClosed },
    data: {
      vizaEdgeType: edge.type,
      config: edge.config ?? {},
    },
    style: edgeStyle(edge.type),
  };
}

function flowNodeToGraphNode(node: VizaFlowNode): VizaGraphNode {
  const graphNode: VizaGraphNode = {
    id: node.id,
    type: node.data.vizaType,
    position: node.position,
    config: node.data.config,
  };

  if (node.data.label) {
    graphNode.label = node.data.label;
  }

  return graphNode;
}

function flowEdgeToGraphEdge(edge: VizaFlowEdge): VizaGraphEdge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: edge.data?.vizaEdgeType ?? "data_flow",
    config: edge.data?.config ?? {},
  };
}

function parseMethodologyGraph(value: unknown): VizaMethodologyGraph {
  if (!isRecord(value)) {
    throw new Error("Graph JSON must be an object.");
  }
  if (value.schema_version !== VIZA_GRAPH_SCHEMA_VERSION) {
    throw new Error(`Graph schema_version must be ${VIZA_GRAPH_SCHEMA_VERSION}.`);
  }
  if (typeof value.methodology_id !== "string" || typeof value.name !== "string") {
    throw new Error("Graph JSON is missing methodology_id or name.");
  }
  if (typeof value.created_at !== "string" || typeof value.updated_at !== "string") {
    throw new Error("Graph JSON is missing timestamps.");
  }
  if (!Array.isArray(value.nodes) || !Array.isArray(value.edges)) {
    throw new Error("Graph JSON must include nodes and edges arrays.");
  }

  const nodes = value.nodes.map(parseGraphNode);
  const edges = value.edges.map(parseGraphEdge);
  return {
    schema_version: VIZA_GRAPH_SCHEMA_VERSION,
    methodology_id: value.methodology_id,
    name: value.name,
    description: typeof value.description === "string" ? value.description : null,
    created_at: value.created_at,
    updated_at: value.updated_at,
    nodes,
    edges,
    metadata: isRecord(value.metadata) ? value.metadata : {},
  };
}

function parseGraphNode(value: unknown): VizaGraphNode {
  if (!isRecord(value)) {
    throw new Error("Every graph node must be an object.");
  }
  const nodeType = readString(value.type);
  if (typeof value.id !== "string" || !isVizaNodeType(nodeType)) {
    throw new Error("Every graph node must include a valid id and type.");
  }
  if (!isRecord(value.position)) {
    throw new Error(`Node ${value.id} is missing a position.`);
  }

  return {
    id: value.id,
    type: nodeType,
    position: {
      x: readNumber(value.position.x, 0),
      y: readNumber(value.position.y, 0),
    },
    label: typeof value.label === "string" ? value.label : null,
    config: isRecord(value.config) ? value.config : {},
  };
}

function parseGraphEdge(value: unknown): VizaGraphEdge {
  if (!isRecord(value)) {
    throw new Error("Every graph edge must be an object.");
  }
  const edgeType = readString(value.type);
  if (
    typeof value.id !== "string" ||
    typeof value.source !== "string" ||
    typeof value.target !== "string" ||
    !isVizaEdgeType(edgeType)
  ) {
    throw new Error("Every graph edge must include a valid id, source, target, and type.");
  }

  return {
    id: value.id,
    source: value.source,
    target: value.target,
    type: edgeType,
    config: isRecord(value.config) ? value.config : {},
  };
}

function inferEdgeType(connection: Connection, nodes: VizaFlowNode[]): VizaEdgeType {
  const sourceNode = nodes.find((node) => node.id === connection.source);
  const targetNode = nodes.find((node) => node.id === connection.target);
  if (
    sourceNode?.data.vizaType === "output_radar" ||
    targetNode?.data.vizaType === "relationship"
  ) {
    return "relationship";
  }
  return "data_flow";
}

function validateCanvasConnection(
  connection: Connection,
  nodes: VizaFlowNode[],
  edges: VizaFlowEdge[],
): string | null {
  if (!connection.source || !connection.target) {
    return "Connection needs both a source and target node.";
  }
  if (connection.source === connection.target) {
    return "Nodes cannot connect to themselves.";
  }

  const sourceNode = nodes.find((node) => node.id === connection.source);
  const targetNode = nodes.find((node) => node.id === connection.target);
  if (!sourceNode || !targetNode) {
    return "Connection references a missing node.";
  }

  if (
    edges.some(
      (edge) =>
        edge.source === connection.source &&
        edge.target === connection.target &&
        edge.sourceHandle === connection.sourceHandle &&
        edge.targetHandle === connection.targetHandle,
    )
  ) {
    return "That edge already exists.";
  }

  if (sourceNode.data.vizaType === "relationship") {
    return "Relationship nodes are terminal outputs.";
  }
  if (targetNode.data.vizaType === "universe") {
    return "Universe nodes do not accept upstream inputs.";
  }
  if (sourceNode.data.vizaType === "output_radar" && targetNode.data.vizaType !== "relationship") {
    return "Output Radar nodes can only connect to Relationship nodes.";
  }
  if (targetNode.data.vizaType === "relationship" && sourceNode.data.vizaType !== "output_radar") {
    return "Relationship nodes should receive Output Radar results.";
  }

  return null;
}

function edgeStyle(type: VizaEdgeType): CSSProperties {
  if (type === "relationship") {
    return { stroke: "#0891b2", strokeWidth: 2 };
  }
  if (type === "evidence") {
    return { stroke: "#b45309", strokeWidth: 2 };
  }
  return { stroke: "#64748b", strokeWidth: 2 };
}

function nodeReadiness(data: VizaCanvasNodeData): NodeReadiness {
  const config = data.config;
  if (data.vizaType === "universe") {
    return readString(config.universe_name) ? "ready" : "not_configured";
  }
  if (data.vizaType === "attribute" || data.vizaType === "filter") {
    return readString(config.attribute_key) ? "ready" : "not_configured";
  }
  if (data.vizaType === "score") {
    return Object.keys(readNumberRecord(config.weights)).length > 0 ? "ready" : "not_configured";
  }
  if (data.vizaType === "output_radar") {
    return readNumber(config.top_n, 0) > 0 ? "ready" : "not_configured";
  }
  if (data.vizaType === "relationship") {
    return readStringArray(config.relationships).length > 0 ? "ready" : "not_configured";
  }
  return "ready";
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tagName = target.tagName.toLowerCase();
  return tagName === "input" || tagName === "textarea" || tagName === "select";
}

function nodeSubtitle(data: VizaCanvasNodeData): string {
  const config = data.config;
  if (data.vizaType === "universe") {
    return readString(config.universe_name, "Universe");
  }
  if (data.vizaType === "attribute") {
    return readableAttributeName(readString(config.attribute_key, "Attribute"));
  }
  if (data.vizaType === "score") {
    return readString(config.method, "weighted_sum").replaceAll("_", " ");
  }
  if (data.vizaType === "output_radar") {
    return `top ${readNumber(config.top_n, 25)}`;
  }
  if (data.vizaType === "transform") {
    return readString(config.transform, "transform").replaceAll("_", " ");
  }
  if (data.vizaType === "filter") {
    return readString(config.operator, "filter").replaceAll("_", " ");
  }
  return readStringArray(config.relationships).slice(0, 2).join(", ") || "relationships";
}

function attributeKeysFromNodes(nodes: VizaFlowNode[]): string[] {
  const keys = nodes
    .filter((node) => node.data.vizaType === "attribute")
    .map((node) => readString(node.data.config.attribute_key))
    .filter(Boolean);

  return Array.from(new Set(keys));
}

function readableAttributeName(
  key: string,
  attributes: VizaAttributeDefinition[] = starterAttributes,
): string {
  return attributes.find((attribute) => attribute.key === key)?.display_name ??
    findAttribute(key)?.display_name ??
    key.replaceAll("_", " ");
}

function scoreWeightLabel(
  key: string,
  attributes: VizaAttributeDefinition[] = starterAttributes,
): string {
  const attribute = attributes.find((item) => item.key === key) ?? findAttribute(key);
  const label = attribute?.display_name ?? key.replaceAll("_", " ");
  if (!attribute) {
    return label;
  }
  if (attribute.evidence_only === true || attribute.contribution_stage === "evidence_only") {
    return `${label} (evidence-only)`;
  }
  if (attribute.production_scoring_allowed === false) {
    return `${label} (restricted)`;
  }
  return label;
}

function connectorStatusClass(status: string): string {
  if (status === "available" || status === "registered") {
    return "available";
  }
  if (status === "credential_required" || status === "not_configured") {
    return "limited";
  }
  return "unavailable";
}

function diagnosticStatusClass(status: string): string {
  if (status === "ok") {
    return "available";
  }
  if (status === "warning" || status === "not_initialized" || status === "checking") {
    return "limited";
  }
  return "unavailable";
}

function summarizeDiagnosticConnectors(diagnostics: VizaRuntimeDiagnostics | null): string {
  if (!diagnostics) {
    return "-";
  }
  const unavailableCount = diagnostics.connector_statuses.filter(
    (connector) =>
      connector.status === "credential_required" ||
      connector.status === "not_configured" ||
      connector.status === "unavailable",
  ).length;
  return `${diagnostics.connector_statuses.length} total, ${unavailableCount} limited`;
}

function summarizeConfigFiles(diagnostics: VizaRuntimeDiagnostics | null): string {
  if (!diagnostics) {
    return "-";
  }
  const missing = diagnostics.config_files.filter((file) => !file.exists);
  if (missing.length) {
    return `${missing.length} missing / ${diagnostics.config_root}`;
  }
  return `${diagnostics.config_files.length} available`;
}

function summarizeInstalledModules(diagnostics: VizaRuntimeDiagnostics | null): string {
  if (!diagnostics?.installed_modules.length) {
    return "-";
  }
  return diagnostics.installed_modules
    .map((module) => readString(module.module_id, "module"))
    .slice(0, 3)
    .join(", ");
}

function summarizeObservationHealth(diagnostics: VizaRuntimeDiagnostics | null): string {
  if (!diagnostics) {
    return "-";
  }
  const health = diagnostics.observation_store_health;
  const count = readNumber(health.observation_count, 0);
  return `${readString(health.status, diagnostics.observation_store_status)} / ${count}`;
}

function summarizeFileHealth(diagnostics: VizaRuntimeDiagnostics | null): string {
  if (!diagnostics) {
    return "-";
  }
  const health = diagnostics.viza_file_health;
  return `${readString(health.status, "unknown")} / ${readNumber(
    health.import_count,
    0,
  )} imports / ${readNumber(health.export_count, 0)} exports`;
}

function summarizeQuarantine(diagnostics: VizaRuntimeDiagnostics | null): string {
  if (!diagnostics || Object.keys(diagnostics.last_quarantine_event).length === 0) {
    return "none";
  }
  return readString(diagnostics.last_quarantine_event.file_id, "quarantined");
}

function exportDiagnosticsBundle(
  diagnostics: VizaRuntimeDiagnostics | null,
  desktopStatus: VizaDesktopStatus | null,
) {
  const sanitizedDesktopStatus = desktopStatus
    ? {
        ...desktopStatus,
        engineToken: desktopStatus.engineToken ? "[redacted]" : "",
      }
    : null;
  downloadText(
    `viza-diagnostics-${new Date().toISOString().slice(0, 10)}.json`,
    JSON.stringify(
      {
        diagnostics,
        desktop: sanitizedDesktopStatus,
        exported_at: new Date().toISOString(),
      },
      null,
      2,
    ) + "\n",
    "application/json",
  );
}

function formatLastRun(projectStore: VizaRuntimeDiagnostics["project_store"] | null): string {
  if (!projectStore?.last_run_id) {
    return "-";
  }
  const timestamp = projectStore.last_run_created_at
    ? ` at ${formatVersionTime(projectStore.last_run_created_at)}`
    : "";
  return `${projectStore.last_run_status ?? "unknown"}${timestamp}`;
}

function shortHash(value: string): string {
  return value ? value.slice(0, 8) : "";
}

function shortVersionId(value: string): string {
  return value.replace(/^version-/, "").slice(0, 8);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error || "unknown error");
}

function formatVersionTime(value: string): string {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp);
}

function versionDiffSummary(
  added: string[],
  removed: string[],
  changed: string[],
): string {
  const parts = [
    added.length ? `+${added.length}` : "",
    removed.length ? `-${removed.length}` : "",
    changed.length ? `${changed.length} changed` : "",
  ].filter(Boolean);
  return parts.join(", ") || "unchanged";
}

function cloneMethodologyGraph(graph: VizaMethodologyGraph): VizaMethodologyGraph {
  const timestamp = new Date().toISOString();
  return {
    ...graph,
    methodology_id: `methodology-${shortId()}`,
    name: `${graph.name} Copy`,
    created_at: timestamp,
    updated_at: timestamp,
    metadata: {
      ...(graph.metadata ?? {}),
      cloned_from_methodology_id: graph.methodology_id,
    },
  };
}

function touchMethodologyGraph(
  graph: VizaMethodologyGraph,
  metadataPatch: Record<string, unknown> = {},
): VizaMethodologyGraph {
  return {
    ...graph,
    updated_at: new Date().toISOString(),
    metadata: {
      ...(graph.metadata ?? {}),
      ...metadataPatch,
    },
  };
}

function latestBatchRunResult(batchResult: VizaBatchExecutionResult): MethodologyRunResult | null {
  for (let index = batchResult.results.length - 1; index >= 0; index -= 1) {
    const result = batchResult.results[index]?.result;
    if (result) {
      return result;
    }
  }
  return null;
}

function resultAttributeColumns(result: MethodologyRunResult | null): string[] {
  if (!result?.rows.length) {
    return [];
  }
  return Array.from(
    new Set(result.rows.flatMap((row) => Object.keys(row.attributes))),
  );
}

function designRadarRows(
  rows: VizaRadarRow[],
  filterText: string,
  sortKey: string,
  sortDirection: RadarSortDirection,
  insightFilters: RadarInsightFilters,
): VizaRadarRow[] {
  const query = filterText.trim().toLowerCase();
  const filteredRows = query
    ? rows.filter((row) =>
        [
          row.ticker,
          row.company_name ?? "",
          row.primary_insight_type ?? "",
          row.translated_summary ?? "",
          row.PIT_status ?? "",
          ...(row.missing_confirmations ?? []),
          ...(row.risk_flags ?? []),
          ...(row.source_restrictions ?? []),
          ...Object.values(row.attributes).map((value) => formatCell(value)),
        ]
          .join(" ")
          .toLowerCase()
          .includes(query),
      )
    : rows;
  const advancedFilteredRows = filteredRows.filter((row) =>
    rowMatchesInsightFilters(row, insightFilters),
  );
  const sortedRows = [...advancedFilteredRows].sort((left, right) => {
    const leftValue = radarSortValue(left, sortKey);
    const rightValue = radarSortValue(right, sortKey);
    if (typeof leftValue === "number" && typeof rightValue === "number") {
      return leftValue - rightValue;
    }
    return String(leftValue).localeCompare(String(rightValue));
  });
  return sortDirection === "descending" ? sortedRows.reverse() : sortedRows;
}

function radarSortValue(row: VizaRadarRow, sortKey: string): number | string {
  if (sortKey === "rank") {
    return row.rank ?? Number.MAX_SAFE_INTEGER;
  }
  if (sortKey === "score") {
    return row.score ?? Number.NEGATIVE_INFINITY;
  }
  if (sortKey === "strategy_fit_score") {
    return row.strategy_fit_score ?? Number.NEGATIVE_INFINITY;
  }
  if (sortKey === "confidence") {
    return row.confidence ?? Number.NEGATIVE_INFINITY;
  }
  if (sortKey === "primary_insight_type") {
    return row.primary_insight_type ?? "";
  }
  if (sortKey === "PIT_status") {
    return row.PIT_status ?? "";
  }
  if (sortKey === "ticker") {
    return row.ticker;
  }
  const value = row.attributes[sortKey];
  if (typeof value === "number" || typeof value === "string") {
    return value;
  }
  if (typeof value === "boolean") {
    return value ? 1 : 0;
  }
  return "";
}

function rowMatchesInsightFilters(row: VizaRadarRow, filters: RadarInsightFilters): boolean {
  const minimumFitScore = parseOptionalNumber(filters.minStrategyFitScore);
  const minimumConfidence = parseOptionalNumber(filters.minConfidence);
  if (minimumFitScore !== null && (row.strategy_fit_score ?? -1) < minimumFitScore) {
    return false;
  }
  if (minimumConfidence !== null && (row.confidence ?? -1) < minimumConfidence) {
    return false;
  }
  if (filters.insightType !== "all" && row.primary_insight_type !== filters.insightType) {
    return false;
  }
  if (
    filters.missingConfirmation !== "all" &&
    !(row.missing_confirmations ?? []).includes(filters.missingConfirmation)
  ) {
    return false;
  }
  if (filters.riskFlag !== "all" && !(row.risk_flags ?? []).includes(filters.riskFlag)) {
    return false;
  }
  if (filters.pitStatus !== "all" && row.PIT_status !== filters.pitStatus) {
    return false;
  }
  return (
    filters.sourceRestriction === "all" ||
    (row.source_restrictions ?? []).includes(filters.sourceRestriction)
  );
}

function buildRadarInsightFilterOptions(
  rows: VizaRadarRow[],
): Record<keyof Omit<RadarInsightFilters, "minConfidence" | "minStrategyFitScore">, string[]> {
  return {
    insightType: uniqueRowValues(rows, (row) => [row.primary_insight_type]),
    missingConfirmation: uniqueRowValues(rows, (row) => row.missing_confirmations ?? []),
    pitStatus: uniqueRowValues(rows, (row) => [row.PIT_status]),
    riskFlag: uniqueRowValues(rows, (row) => row.risk_flags ?? []),
    sourceRestriction: uniqueRowValues(rows, (row) => row.source_restrictions ?? []),
  };
}

function uniqueRowValues(
  rows: VizaRadarRow[],
  selector: (row: VizaRadarRow) => Array<string | null | undefined>,
): string[] {
  return Array.from(
    new Set(
      rows
        .flatMap(selector)
        .filter((value): value is string => typeof value === "string" && value.length > 0),
    ),
  ).sort((left, right) => left.localeCompare(right));
}

function parseOptionalNumber(value: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsedValue = Number(value);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

function radarScorecard(rows: VizaRadarRow[]): {
  averageScore: string;
  topTicker: string;
} {
  const scores = rows
    .map((row) => row.score)
    .filter((score): score is number => typeof score === "number" && Number.isFinite(score));
  const averageScore = scores.length
    ? (scores.reduce((total, score) => total + score, 0) / scores.length).toFixed(3)
    : "-";
  return {
    averageScore,
    topTicker: rows[0]?.ticker ?? "-",
  };
}

function attributeMatchesSearch(attribute: VizaAttributeDefinition, searchText: string): boolean {
  const query = searchText.trim().toLowerCase();
  if (!query) {
    return true;
  }
  return [
    attribute.key,
    attribute.display_name,
    attribute.description,
    attribute.family,
    attribute.source,
    attribute.unit,
    attribute.source_type,
    attribute.coverage,
    attribute.contribution_stage,
  ]
    .filter((value): value is string => typeof value === "string")
    .some((value) => value.toLowerCase().includes(query));
}

function uniqueAttributeValues(
  attributes: VizaAttributeDefinition[],
  key: keyof VizaAttributeDefinition,
): string[] {
  return Array.from(
    new Set(
      attributes
        .map((attribute) => attribute[key])
        .filter((value): value is string => typeof value === "string" && value.length > 0),
    ),
  ).sort((left, right) => left.localeCompare(right));
}

function isAttributeLocked(attribute: VizaAttributeDefinition): boolean {
  const entitlementPolicy = (attribute.entitlement_policy ?? "internal").toLowerCase();
  const limitedEntitlementTokens = [
    "denied",
    "disabled",
    "locked",
    "restricted",
    "unavailable",
    "credential_required",
    "license_required",
  ];
  return (
    (attribute.deprecation_status !== undefined && attribute.deprecation_status !== "active") ||
    limitedEntitlementTokens.some((token) => entitlementPolicy.includes(token))
  );
}

function isTerminalJobStatus(status: string): boolean {
  return ["cancelled", "completed", "failed"].includes(status);
}

function isSourceBackedAttribute(attribute: VizaAttributeDefinition): boolean {
  const implementationStatus = readString(attribute.diagnostics?.implementation_status).toLowerCase();
  return (
    implementationStatus.includes("source_backed") ||
    (attribute.source_type === "local_csv" &&
      attribute.availability_function.toLowerCase().includes("observation"))
  );
}

function isPrototypeFallbackAttribute(attribute: VizaAttributeDefinition): boolean {
  if (isSourceBackedAttribute(attribute)) {
    return false;
  }
  const implementationStatus = readString(attribute.diagnostics?.implementation_status).toLowerCase();
  return (
    implementationStatus.includes("prototype") ||
    readString(attribute.model_version).toLowerCase().includes("prototype") ||
    readString(attribute.data_version).toLowerCase().includes("prototype") ||
    readString(attribute.freshness).toLowerCase().includes("prototype")
  );
}

function isExportRestrictedAttribute(attribute: VizaAttributeDefinition): boolean {
  const policy = readString(attribute.entitlement_policy, "internal").toLowerCase();
  return ["no_export", "query_only", "redacted", "restricted"].some((token) =>
    policy.includes(token),
  );
}

function connectorMappingForAttribute(attribute: VizaAttributeDefinition): string | null {
  const mapping = readString(attribute.diagnostics?.connector_mapping_path);
  if (mapping) {
    return mapping;
  }
  if (!isSourceBackedAttribute(attribute) && !isExportRestrictedAttribute(attribute)) {
    return null;
  }
  return `${attribute.source} -> ${attribute.availability_function}`;
}

function readableHeader(key: string): string {
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatCell(value: number | string | boolean | null | undefined): string {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return value ?? "";
}

function formatEvidenceValue(value: unknown): string {
  if (typeof value === "number" || typeof value === "string" || typeof value === "boolean") {
    return formatCell(value);
  }
  if (value === null || value === undefined) {
    return "";
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatEvidenceValue(item)).join(", ");
  }
  return JSON.stringify(value);
}

function downloadGraph(graph: VizaMethodologyGraph) {
  const blob = new Blob([JSON.stringify(graph, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${slugify(graph.name)}.viza.json`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function sourceRightsFromRunResult(result: MethodologyRunResult | null): Record<string, unknown>[] {
  const connectors = isRecord(result?.manifest.connectors) ? result.manifest.connectors : {};
  return Object.entries(connectors).flatMap(([connectorId, connector]) => {
    if (!connectorId || !isRecord(connector)) {
      return [];
    }
    const entitlement = isRecord(connector.entitlement) ? connector.entitlement : {};
    return [
      {
        connector_id: connectorId,
        source_id: connectorId,
        license_policy: readString(connector.license_policy, "unknown"),
        export_allowed: readBoolean(entitlement.export_allowed, true),
        redistribution_allowed: readBoolean(entitlement.redistribution_allowed, false),
      },
    ];
  });
}

function compactPath(path: string): string {
  const normalized = path.replaceAll("\\", "/");
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length <= 2) {
    return path;
  }
  return `${parts.at(-2)}/${parts.at(-1)}`;
}

function downloadText(filename: string, payload: string, contentType: string) {
  const blob = new Blob([payload], { type: contentType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function readString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function readNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function readBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function readExportAllowed(record: Record<string, unknown>): boolean | null {
  const entitlement = isRecord(record.entitlement) ? record.entitlement : {};
  if (typeof entitlement.export_allowed === "boolean") {
    return entitlement.export_allowed;
  }
  const rightsPolicy = isRecord(record.rights_policy) ? record.rights_policy : {};
  if (typeof rightsPolicy.export_allowed === "boolean") {
    return rightsPolicy.export_allowed;
  }
  const exportPolicy = rightsPolicy.export_policy;
  if (typeof exportPolicy === "string") {
    const policy = exportPolicy.toLowerCase();
    return !["blocked", "no_export", "restricted"].some((token) => policy.includes(token));
  }
  return null;
}

function readStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function readNumberRecord(value: unknown): Record<string, number> {
  if (!isRecord(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).filter(
      (entry): entry is [string, number] => typeof entry[1] === "number",
    ),
  );
}

function parseCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readStoredStringArray(key: string): string[] {
  try {
    const storedValue = window.localStorage.getItem(key);
    if (!storedValue) {
      return [];
    }
    const parsedValue: unknown = JSON.parse(storedValue);
    return readStringArray(parsedValue);
  } catch {
    return [];
  }
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function writeStoredStringArray(key: string, value: string[]) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Attribute shortcuts are convenience state; failed storage should not block editing.
  }
}

function moveToFront(values: string[], value: string, limit: number): string[] {
  return [value, ...values.filter((item) => item !== value)].slice(0, limit);
}

function toggleStringMembership(values: string[], value: string): string[] {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [value, ...values].slice(0, 24);
}

function shortId(): string {
  return crypto.randomUUID().slice(0, 8);
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80) || "untitled-methodology";
}
