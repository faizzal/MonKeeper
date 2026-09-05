import React, {
  useEffect,
  useMemo,
  useState
} from "react";

import ReactDOM from "react-dom/client";
import axios from "axios";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from "chart.js";

import {
  Line
} from "react-chartjs-2";

import "./styles.css";


ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);


const API_BASE = "/api";
const AUTO_REFRESH_MS = 15000;


/*
============================================================
Chart Colors
============================================================
*/

const NODE_COLORS = {
  solr1: "#2563eb",
  solr2: "#f97316"
};


const FALLBACK_NODE_COLORS = [
  "#16a34a",
  "#9333ea",
  "#dc2626",
  "#0891b2",
  "#ca8a04",
  "#db2777"
];


function getNodeColor(
  hostname,
  index = 0
) {
  if (
    hostname &&
    NODE_COLORS[hostname]
  ) {
    return NODE_COLORS[hostname];
  }

  return FALLBACK_NODE_COLORS[
    index %
    FALLBACK_NODE_COLORS.length
  ];
}


/*
============================================================
Helpers
============================================================
*/

function safeNumber(
  value,
  fallback = 0
) {
  const number = Number(value);

  return Number.isFinite(number)
    ? number
    : fallback;
}


function fmt(
  value,
  decimals = 1
) {
  if (
    value === null ||
    value === undefined
  ) {
    return "N/A";
  }

  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "N/A";
  }

  return number.toFixed(
    decimals
  );
}


/*
============================================================
Application
============================================================
*/
function getClusterFreshness(cluster) {
  if (!cluster) {
    return {
      status: "UNKNOWN",
      ageSeconds: null
    };
  }

  if (cluster.enabled === false) {
    return {
      status: "DISABLED",
      ageSeconds: null
    };
  }

  if (!cluster.last_metric_at) {
    return {
      status: "STALE",
      ageSeconds: null
    };
  }

  const metricTime =
    new Date(cluster.last_metric_at);

  const now =
    new Date();

  const ageSeconds =
    Math.max(
      0,
      Math.floor(
        (
          now.getTime() -
          metricTime.getTime()
        ) / 1000
      )
    );

  return {
    status:
      ageSeconds <= 60
        ? "FRESH"
        : "STALE",

    ageSeconds:
      ageSeconds
  };
}
function App() {

  const [
    clusters,
    setClusters
  ] = useState([]);
 
  const [
   selectedClusterId,
   setSelectedClusterId
  ] = useState(null);

  const [
    nodes,
    setNodes
  ] = useState([]);

  const [
    currentMetrics,
    setCurrentMetrics
  ] = useState([]);

  const [
    history,
    setHistory
  ] = useState({});

  const [
    solrSummary,
    setSolrSummary
  ] = useState(null);

  const [
    topology,
    setTopology
  ] = useState(null);

  const [
    consistency,
    setConsistency
  ] = useState(null);

  const [
    requestSummary,
    setRequestSummary
  ] = useState(null);

  const [
    requestHistory,
    setRequestHistory
  ] = useState([]);

  const [
    loading,
    setLoading
  ] = useState(true);

  const [
    refreshing,
    setRefreshing
  ] = useState(false);

  const [
    lastUpdated,
    setLastUpdated
  ] = useState(null);

  const [
    error,
    setError
  ] = useState(null);
const [
  activeView,
  setActiveView
] = useState("dashboard");
const [
  showAddCluster,
  setShowAddCluster
] = useState(false);

const [
  newCluster,
  setNewCluster
] = useState({
  name: "",
  environment: "lab",
  zk_connection_string: "",
  zk_chroot: "/solr",
  solr_scheme: "http",
  solr_port: 8983,
  discovery_interval: 60
});
const [
  credentialsCluster,
  setCredentialsCluster
] = useState(null);

const [
  credentialsForm,
  setCredentialsForm
] = useState({
  username: "",
  password: ""
});

const [
  credentialsSaving,
  setCredentialsSaving
] = useState(false);

const [
  credentialsMessage,
  setCredentialsMessage
] = useState("");

const [
  editingCluster,
  setEditingCluster
] = useState(null);

const [
  editClusterForm,
  setEditClusterForm
] = useState({
  name: "",
  environment: "",
  zk_connection_string: "",
  zk_chroot: "/solr",
  solr_scheme: "http",
  solr_port: 8983,
  discovery_interval: 60
});

const [
  editClusterSaving,
  setEditClusterSaving
] = useState(false);

const [
  editClusterMessage,
  setEditClusterMessage
] = useState("");

const [
  deleteClusterTarget,
  setDeleteClusterTarget
] = useState(null);

const [
  deleteClusterConfirm,
  setDeleteClusterConfirm
] = useState("");

const [
  deleteClusterSaving,
  setDeleteClusterSaving
] = useState(false);

const [
  deleteClusterMessage,
  setDeleteClusterMessage
] = useState("");
  /*
  ==========================================================
  Data Loader
  ==========================================================
  */

const updateCluster = async () => {
  if (!editingCluster) {
    return;
  }

  if (!editClusterForm.name.trim()) {
    setEditClusterMessage(
      "Cluster name is required."
    );
    return;
  }

  if (!editClusterForm.zk_connection_string.trim()) {
    setEditClusterMessage(
      "ZooKeeper connection string is required."
    );
    return;
  }

  try {
    setEditClusterSaving(true);
    setEditClusterMessage("");

    await axios.put(
      `${API_BASE}/clusters/${editingCluster.id}`,
      {
        name:
          editClusterForm.name.trim(),

        environment:
          editClusterForm.environment,

        zk_connection_string:
          editClusterForm.zk_connection_string.trim(),

        zk_chroot:
          editClusterForm.zk_chroot.trim() || "/solr",

        solr_scheme:
          editClusterForm.solr_scheme,

        solr_port:
          Number(editClusterForm.solr_port),

        discovery_interval:
          Number(editClusterForm.discovery_interval)
      }
    );

    setEditClusterMessage(
      "Cluster updated successfully."
    );

    await loadData();

    setEditingCluster(null);

  } catch (err) {
    console.error(
      "Failed to update cluster:",
      err
    );

    setEditClusterMessage(
      err.response?.data?.detail ||
      "Failed to update cluster."
    );

  } finally {
    setEditClusterSaving(false);
  }
};

const saveCredentials = async () => {
  if (!credentialsCluster) {
    return;
  }

  if (!credentialsForm.username.trim()) {
    setCredentialsMessage(
      "Solr username is required."
    );
    return;
  }

  if (!credentialsForm.password) {
    setCredentialsMessage(
      "Solr password is required."
    );
    return;
  }

  try {
    setCredentialsSaving(true);
    setCredentialsMessage("");

    const response = await axios.put(
      `${API_BASE}/clusters/${credentialsCluster.id}/credentials`,
      {
        username: credentialsForm.username.trim(),
        password: credentialsForm.password
      }
    );

    setCredentialsMessage(
      response.data?.message ||
      "Credentials verified and saved successfully."
    );

    await loadData();

    setCredentialsForm({
      username: credentialsForm.username.trim(),
      password: ""
    });
setCredentialsCluster(
  prev =>
    prev
      ? {
          ...prev,
          solr_username:
            credentialsForm.username.trim(),
          credentials_configured: true
        }
      : prev
);

  } catch (err) {
    console.error(
      "Failed to save credentials:",
      err
    );

    setCredentialsMessage(
      err.response?.data?.detail ||
      "Failed to verify Solr credentials."
    );

  } finally {
    setCredentialsSaving(false);
  }
};
const toggleClusterEnabled = async (
  cluster
) => {
  try {
    setError(null);

    const newEnabled =
      !cluster.enabled;

    await axios.patch(
      `${API_BASE}/clusters/${cluster.id}/enabled`,
      null,
      {
        params: {
          enabled:
            newEnabled
        }
      }
    );

    await loadData();

  } catch (err) {
    setError(
      err?.response?.data?.detail ||
      err.message ||
      "Unable to update cluster status"
    );
  }
};
const deleteCluster = async () => {
  if (!deleteClusterTarget) {
    return;
  }

  if (
    deleteClusterConfirm !==
    deleteClusterTarget.name
  ) {
    setDeleteClusterMessage(
      "Cluster name does not match."
    );
    return;
  }

  try {
    setDeleteClusterSaving(true);
    setDeleteClusterMessage("");

    await axios.delete(
      `${API_BASE}/clusters/${deleteClusterTarget.id}`
    );

    const deletedId =
      deleteClusterTarget.id;

    setDeleteClusterTarget(null);
    setDeleteClusterConfirm("");

    if (
      Number(selectedClusterId) ===
      Number(deletedId)
    ) {
      setSelectedClusterId(null);
    }

    await loadData();

  } catch (err) {
    setDeleteClusterMessage(
      err?.response?.data?.detail ||
      err.message ||
      "Unable to delete cluster"
    );

  } finally {
    setDeleteClusterSaving(false);
  }
};	
  const loadData = async (
    manualRefresh = false
  ) => {

    try {

      if (manualRefresh) {
        setRefreshing(true);
      }

      setError(null);

      const [
        clustersRes,
        nodesRes,
        metricsRes
      ] = await Promise.all([

        axios.get(
          `${API_BASE}/clusters`
        ),

        axios.get(
          `${API_BASE}/nodes`
        ),

        axios.get(
          `${API_BASE}/metrics/solr/current`
        )

      ]);

      const clusterList =
        clustersRes.data.clusters ||
        [];

      const allNodes =
        nodesRes.data.nodes ||
        [];

      const allMetrics =
        metricsRes.data.metrics ||
        [];


      setClusters(
        clusterList
      );


      const clusterId =
        selectedClusterId ||
        (
          clusterList.length > 0
            ? clusterList[0].id
            : 1
        );


      if (
        selectedClusterId === null &&
        clusterList.length > 0
      ) {
        setSelectedClusterId(
          clusterList[0].id
        );
      }


      const nodeList =
        allNodes.filter(
          node =>
            Number(node.cluster_id) ===
            Number(clusterId)
        );


      const metricsList =
        allMetrics.filter(
          metric =>
            Number(metric.cluster_id) ===
            Number(clusterId)
        );


      setNodes(
        nodeList
      );

      setCurrentMetrics(
        metricsList
      );


      /*
      --------------------------------------------------------
      JVM History
      --------------------------------------------------------
      */

      const historyMap = {};


      await Promise.all(

        metricsList.map(
          async metric => {

            try {

              const response =
                await axios.get(
                  `${API_BASE}/metrics/solr/history`,
                  {
                    params: {
                      node_id:
                        metric.node_id,

                      minutes:
                        60
                    }
                  }
                );


              historyMap[
                metric.node_id
              ] =
                response
                  .data
                  .history ||
                [];

            } catch {

              historyMap[
                metric.node_id
              ] = [];

            }

          }
        )

      );


      setHistory(
        historyMap
      );


      /*
      --------------------------------------------------------
      Optional Solr APIs
      --------------------------------------------------------
      */

      const optionalRequests =
        await Promise.allSettled([

          axios.get(
            `${API_BASE}/solr/summary`,
            {
              params: {
                cluster_id:
                  clusterId
              }
            }
          ),

          axios.get(
            `${API_BASE}/solr/topology`,
            {
              params: {
                cluster_id:
                  clusterId
              }
            }
          ),

          axios.get(
            `${API_BASE}/solr/consistency`,
            {
              params: {
                cluster_id:
                  clusterId
              }
            }
          ),

          axios.get(
            `${API_BASE}/metrics/requests/summary`,
            {
              params: {
                cluster_id:
                  clusterId
              }
            }
          ),

          axios.get(
            `${API_BASE}/metrics/requests/history`,
            {
              params: {
                cluster_id:
                  clusterId,

                minutes:
                  60
              }
            }
          )

        ]);


      if (
        optionalRequests[0]
          .status ===
        "fulfilled"
      ) {

        setSolrSummary(
          optionalRequests[0]
            .value
            .data
        );

      }


      if (
        optionalRequests[1]
          .status ===
        "fulfilled"
      ) {

        setTopology(
          optionalRequests[1]
            .value
            .data
        );

      }


      if (
        optionalRequests[2]
          .status ===
        "fulfilled"
      ) {

        setConsistency(
          optionalRequests[2]
            .value
            .data
        );

      }


      if (
        optionalRequests[3]
          .status ===
        "fulfilled"
      ) {

        setRequestSummary(
          optionalRequests[3]
            .value
            .data
        );

      }


      if (
        optionalRequests[4]
          .status ===
        "fulfilled"
      ) {

        setRequestHistory(
          optionalRequests[4]
            .value
            .data
            .history ||
          []
        );

      }


      setLastUpdated(
        new Date()
      );

      setLoading(
        false
      );

    } catch (err) {

      setError(
        err?.response?.data?.detail ||
        err.message ||
        "Unable to load MonKeeper data"
      );

      setLoading(
        false
      );

    } finally {

      setRefreshing(
        false
      );

    }

  };


  /*
  ==========================================================
  Auto Refresh
  ==========================================================
  */

  useEffect(
    () => {

      loadData();

      const timer =
        setInterval(
          () => loadData(),
          AUTO_REFRESH_MS
        );


      return () =>
        clearInterval(
          timer
        );

    },
    [
	selectedClusterId
    ]
  );


  /*
  ==========================================================
  Node Groups
  ==========================================================
  */

  const solrNodes =
    useMemo(
      () =>
        nodes.filter(
          node =>
            node.node_type ===
            "solr"
        ),
      [
        nodes
      ]
    );


  const zkNodes =
    useMemo(
      () =>
        nodes.filter(
          node =>
            node.node_type ===
            "zookeeper"
        ),
      [
        nodes
      ]
    );


  const upNodes =
    nodes.filter(
      node =>
        node.status ===
        "UP"
    ).length;


  const overallHealthy =
    solrSummary
      ? solrSummary
          .overall_status ===
        "HEALTHY"
      : (
          nodes.length > 0 &&
          upNodes ===
            nodes.length
        );


const primaryCluster =
  clusters.find(
    cluster =>
      Number(cluster.id) ===
      Number(selectedClusterId)
  ) ||
  (
    clusters.length > 0
      ? clusters[0]
      : null
  );
const clusterFreshness =
  getClusterFreshness(
    primaryCluster
  );

  /*
  ==========================================================
  Chart Labels
  ==========================================================
  */

  const baseHistory =
    currentMetrics.length > 0
      ? (
          history[
            currentMetrics[0]
              .node_id
          ] ||
          []
        )
      : [];


  /*
  ==========================================================
  Heap Chart
  ==========================================================
  */

  const heapChartData = {

    labels:
      baseHistory.map(
        item =>
          new Date(
            item.collected_at
          ).toLocaleTimeString()
      ),

    datasets:
      currentMetrics.map(
        (
          metric,
          index
        ) => {

          const nodeColor =
            getNodeColor(
              metric.hostname,
              index
            );


          return {

            label:
              metric.hostname,

            data:
              (
                history[
                  metric.node_id
                ] ||
                []
              ).map(
                item =>
                  safeNumber(
                    item
                      .heap_usage_percent
                  )
              ),

            borderColor:
              nodeColor,

            backgroundColor:
              nodeColor,

            pointBackgroundColor:
              nodeColor,

            pointBorderColor:
              nodeColor,

            pointHoverBackgroundColor:
              nodeColor,

            pointHoverBorderColor:
              "#ffffff",

            borderWidth:
              2.5,

            tension:
              0.25,

            pointRadius:
              1.5,

            pointHoverRadius:
              5,

            fill:
              false

          };

        }
      )

  };


  /*
  ==========================================================
  CPU Chart
  ==========================================================
  */

  const cpuChartData = {

    labels:
      baseHistory.map(
        item =>
          new Date(
            item.collected_at
          ).toLocaleTimeString()
      ),

    datasets:
      currentMetrics.map(
        (
          metric,
          index
        ) => {

          const nodeColor =
            getNodeColor(
              metric.hostname,
              index
            );


          return {

            label:
              metric.hostname,

            data:
              (
                history[
                  metric.node_id
                ] ||
                []
              ).map(
                item =>
                  safeNumber(
                    item
                      .process_cpu_percent
                  )
              ),

            borderColor:
              nodeColor,

            backgroundColor:
              nodeColor,

            pointBackgroundColor:
              nodeColor,

            pointBorderColor:
              nodeColor,

            pointHoverBackgroundColor:
              nodeColor,

            pointHoverBorderColor:
              "#ffffff",

            borderWidth:
              2.5,

            tension:
              0.25,

            pointRadius:
              1.5,

            pointHoverRadius:
              5,

            fill:
              false

          };

        }
      )

  };


  /*
  ==========================================================
  Request Rate Chart
  ==========================================================
  */

  const requestRateChartData = {

    labels:
      requestHistory.map(
        item =>
          new Date(
            item.collected_at
          ).toLocaleTimeString()
      ),

    datasets: [

      {

        label:
          "Request Rate (1m)",

        data:
          requestHistory.map(
            item =>
              safeNumber(
                item.rate_1m
              )
          ),

        borderColor:
          "#0891b2",

        backgroundColor:
          "#0891b2",

        pointBackgroundColor:
          "#0891b2",

        pointBorderColor:
          "#0891b2",

        borderWidth:
          2.5,

        tension:
          0.25,

        pointRadius:
          2,

        pointHoverRadius:
          5,

        fill:
          false

      }

    ]

  };


  /*
  ==========================================================
  P95 / P99 Chart
  ==========================================================
  */

  const latencyChartData = {

    labels:
      requestHistory.map(
        item =>
          new Date(
            item.collected_at
          ).toLocaleTimeString()
      ),

    datasets: [

      {

        label:
          "P95",

        data:
          requestHistory.map(
            item =>
              safeNumber(
                item.max_p95_ms
              )
          ),

        borderColor:
          "#2563eb",

        backgroundColor:
          "#2563eb",

        pointBackgroundColor:
          "#2563eb",

        pointBorderColor:
          "#2563eb",

        borderWidth:
          2.5,

        tension:
          0.25,

        pointRadius:
          2,

        pointHoverRadius:
          5,

        fill:
          false

      },

      {

        label:
          "P99",

        data:
          requestHistory.map(
            item =>
              safeNumber(
                item.max_p99_ms
              )
          ),

        borderColor:
          "#dc2626",

        backgroundColor:
          "#dc2626",

        pointBackgroundColor:
          "#dc2626",

        pointBorderColor:
          "#dc2626",

        borderWidth:
          2.5,

        tension:
          0.25,

        pointRadius:
          2,

        pointHoverRadius:
          5,

        fill:
          false

      }

    ]

  };


  /*
  ==========================================================
  Chart Options
  ==========================================================
  */

  const chartOptions = {

    responsive:
      true,

    maintainAspectRatio:
      false,

    interaction: {

      intersect:
        false,

      mode:
        "index"

    },

    plugins: {

      legend: {

        position:
          "top",

        labels: {

          color:
            "#334155",

          usePointStyle:
            true,

          pointStyle:
            "circle",

          boxWidth:
            10,

          boxHeight:
            10,

          padding:
            16,

          font: {

            size:
              12,

            weight:
              "600"

          }

        }

      },

      tooltip: {

        backgroundColor:
          "#0f172a",

        titleColor:
          "#ffffff",

        bodyColor:
          "#e2e8f0",

        padding:
          10,

        cornerRadius:
          8,

        displayColors:
          true

      }

    },

    scales: {

      x: {

        ticks: {

          color:
            "#64748b",

          maxTicksLimit:
            8

        },

        grid: {

          color:
            "rgba(148, 163, 184, 0.18)"

        },

        border: {

          color:
            "#cbd5e1"

        }

      },

      y: {

        beginAtZero:
          true,

        ticks: {

          color:
            "#64748b"

        },

        grid: {

          color:
            "rgba(148, 163, 184, 0.20)"

        },

        border: {

          color:
            "#cbd5e1"

        }

      }

    }

  };
  const createCluster = async () => {
    try {
      setError(null);

      if (!newCluster.name.trim()) {
        setError(
          "Cluster name is required"
        );
        return;
      }

      if (
        !newCluster
          .zk_connection_string
          .trim()
      ) {
        setError(
          "ZooKeeper connection string is required"
        );
        return;
      }

      await axios.post(
        `${API_BASE}/clusters`,
        {
          name:
            newCluster.name.trim(),

          environment:
            newCluster.environment,

          zk_connection_string:
            newCluster
              .zk_connection_string
              .trim(),

          zk_chroot:
            newCluster.zk_chroot ||
            "/solr",

          solr_scheme:
            newCluster.solr_scheme,

          solr_port:
            Number(
              newCluster.solr_port
            ),

          discovery_interval:
            Number(
              newCluster
                .discovery_interval
            )
        }
      );

      setShowAddCluster(
        false
      );

      setNewCluster({
        name: "",
        environment: "lab",
        zk_connection_string: "",
        zk_chroot: "/solr",
        solr_scheme: "http",
        solr_port: 8983,
        discovery_interval: 60
      });

      await loadData(
        true
      );

    } catch (err) {
      setError(
        err?.response?.data?.detail ||
        err.message ||
        "Unable to create cluster"
      );
    }
  };

  /*
  ==========================================================
  Loading Screen
  ==========================================================
  */
if (activeView === "clusters") {
  return (
    <div className="app-shell">

      <header className="topbar">
        <div>
          <h1>MonKeeper</h1>
          <p>SolrCloud & ZooKeeper Monitoring</p>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="nav-button"
            onClick={() => setActiveView("dashboard")}
          >
            Dashboard
          </button>

          <button
            type="button"
            className="nav-button active"
          >
            Manage Clusters
          </button>
        </div>
      </header>

      <main className="dashboard">

        <div className="section-header">
          <div>
            <h2>Cluster Management</h2>
            <p>
              Configure and manage monitored SolrCloud clusters.
            </p>
          </div>

          <button
            type="button"
            className="primary-action"
		onClick={() => setShowAddCluster(true)}
          >
            + Add Cluster
          </button>
{showAddCluster && (
  <div className="cluster-form-card">

    <div className="cluster-form-header">
      <div>
        <h3>Add New Cluster</h3>
        <p>Configure a new SolrCloud cluster for monitoring.</p>
      </div>

      <button
        type="button"
        onClick={() => setShowAddCluster(false)}
      >
        Cancel
      </button>
    </div>

    <div className="cluster-form-grid">

      <label>
        Cluster Name
        <input
          type="text"
          placeholder="Production SolrCloud"
          value={newCluster.name}
          onChange={(e) =>
            setNewCluster({
              ...newCluster,
              name: e.target.value
            })
          }
        />
      </label>

      <label>
        Environment
        <select
          value={newCluster.environment}
          onChange={(e) =>
            setNewCluster({
              ...newCluster,
              environment: e.target.value
            })
          }
        >
          <option value="lab">Lab</option>
          <option value="dev">Development</option>
          <option value="test">Test</option>
          <option value="staging">Staging</option>
          <option value="production">Production</option>
        </select>
      </label>

      <label>
        ZooKeeper Connection String
        <input
          type="text"
          placeholder="zk1:2181,zk2:2181,zk3:2181"
          value={newCluster.zk_connection_string}
          onChange={(e) =>
            setNewCluster({
              ...newCluster,
              zk_connection_string: e.target.value
            })
          }
        />
      </label>

      <label>
        ZooKeeper Chroot
        <input
          type="text"
          placeholder="/solr"
          value={newCluster.zk_chroot}
          onChange={(e) =>
            setNewCluster({
              ...newCluster,
              zk_chroot: e.target.value
            })
          }
        />
      </label>

      <label>
        Solr Scheme
        <select
          value={newCluster.solr_scheme}
          onChange={(e) =>
            setNewCluster({
              ...newCluster,
              solr_scheme: e.target.value
            })
          }
        >
          <option value="http">HTTP</option>
          <option value="https">HTTPS</option>
        </select>
      </label>

      <label>
        Solr Port
        <input
          type="number"
          min="1"
          max="65535"
          value={newCluster.solr_port}
          onChange={(e) =>
            setNewCluster({
              ...newCluster,
              solr_port: Number(e.target.value)
            })
          }
        />
      </label>

      <label>
        Discovery Interval (seconds)
        <input
          type="number"
          min="10"
          value={newCluster.discovery_interval}
          onChange={(e) =>
            setNewCluster({
              ...newCluster,
              discovery_interval: Number(e.target.value)
            })
          }
        />
      </label>

    </div>

    <div className="cluster-form-actions">
      <button
        type="button"
        onClick={() => setShowAddCluster(false)}
      >
        Cancel
      </button>

      <button
        type="button"
        className="primary-button"
	onClick={createCluster}
      >
        Create Cluster
      </button>
    </div>

  </div>
)}
        </div>
{editingCluster && (
  <div className="cluster-form-card">

    <div className="cluster-form-header">
      <div>
        <h3>Edit Cluster</h3>
        <p>
          Update configuration for{" "}
          <strong>{editingCluster.name}</strong>
        </p>
      </div>

      <button
        type="button"
        onClick={() => {
          setEditingCluster(null);
          setEditClusterMessage("");
        }}
      >
        Cancel
      </button>
    </div>

    <div className="cluster-form-grid">

      <label>
        Cluster Name
        <input
          type="text"
          value={editClusterForm.name}
          onChange={(e) =>
            setEditClusterForm({
              ...editClusterForm,
              name: e.target.value
            })
          }
        />
      </label>

      <label>
        Environment
        <select
          value={editClusterForm.environment}
          onChange={(e) =>
            setEditClusterForm({
              ...editClusterForm,
              environment: e.target.value
            })
          }
        >
          <option value="lab">Lab</option>
          <option value="dev">Development</option>
          <option value="test">Test</option>
          <option value="staging">Staging</option>
          <option value="production">Production</option>
        </select>
      </label>

      <label>
        ZooKeeper Connection String
        <input
          type="text"
          value={editClusterForm.zk_connection_string}
          onChange={(e) =>
            setEditClusterForm({
              ...editClusterForm,
              zk_connection_string: e.target.value
            })
          }
        />
      </label>

      <label>
        ZooKeeper Chroot
        <input
          type="text"
          value={editClusterForm.zk_chroot}
          onChange={(e) =>
            setEditClusterForm({
              ...editClusterForm,
              zk_chroot: e.target.value
            })
          }
        />
      </label>

      <label>
        Solr Scheme
        <select
          value={editClusterForm.solr_scheme}
          onChange={(e) =>
            setEditClusterForm({
              ...editClusterForm,
              solr_scheme: e.target.value
            })
          }
        >
          <option value="http">HTTP</option>
          <option value="https">HTTPS</option>
        </select>
      </label>

      <label>
        Solr Port
        <input
          type="number"
          min="1"
          max="65535"
          value={editClusterForm.solr_port}
          onChange={(e) =>
            setEditClusterForm({
              ...editClusterForm,
              solr_port: Number(e.target.value)
            })
          }
        />
      </label>

      <label>
        Discovery Interval (seconds)
        <input
          type="number"
          min="10"
          value={editClusterForm.discovery_interval}
          onChange={(e) =>
            setEditClusterForm({
              ...editClusterForm,
              discovery_interval: Number(e.target.value)
            })
          }
        />
      </label>

    </div>

    {editClusterMessage && (
      <div
        style={{
          marginTop: "12px",
          padding: "10px 12px",
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          fontSize: "12px"
        }}
      >
        {editClusterMessage}
      </div>
    )}

    <div className="cluster-form-actions">

      <button
        type="button"
        onClick={() => {
          setEditingCluster(null);
          setEditClusterMessage("");
        }}
      >
        Cancel
      </button>

      <button
        type="button"
        className="primary-button"
        disabled={editClusterSaving}
onClick={updateCluster}
      >
        {editClusterSaving
          ? "Saving..."
          : "Save Changes"}
      </button>

    </div>

  </div>
)}
        {credentialsCluster && (
  <div className="cluster-form-card">

    <div className="cluster-form-header">
      <div>
        <h3>Solr Credentials</h3>

        <p>
          Verify and securely store credentials for{" "}
          <strong>{credentialsCluster.name}</strong>
        </p>
      </div>

      <button
        type="button"
        onClick={() => {
          setCredentialsCluster(null);
          setCredentialsMessage("");
          setCredentialsForm({
            username: "",
            password: ""
          });
        }}
      >
        Cancel
      </button>
    </div>

    <div className="cluster-form-grid">

      <label>
        Solr Username

        <input
          type="text"
          autoComplete="username"
          value={credentialsForm.username}
          onChange={(e) =>
            setCredentialsForm({
              ...credentialsForm,
              username: e.target.value
            })
          }
        />
      </label>

      <label>
        Solr Password

        <input
          type="password"
          autoComplete="new-password"
          placeholder="Enter Solr password"
          value={credentialsForm.password}
          onChange={(e) =>
            setCredentialsForm({
              ...credentialsForm,
              password: e.target.value
            })
          }
        />
      </label>

    </div>

    <div
      style={{
        marginTop: "14px",
        fontSize: "12px",
        color: credentialsCluster.credentials_configured
          ? "#15803d"
          : "#b45309"
      }}
    >
      Status:{" "}
      {credentialsCluster.credentials_configured
        ? "Credentials configured"
        : "Credentials not configured"}
    </div>

    {credentialsMessage && (
      <div
        style={{
          marginTop: "12px",
          padding: "10px 12px",
          background: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          fontSize: "12px"
        }}
      >
        {credentialsMessage}
      </div>
    )}

    <div className="cluster-form-actions">

      <button
        type="button"
        onClick={() => {
          setCredentialsCluster(null);
          setCredentialsMessage("");
        }}
      >
        Cancel
      </button>

      <button
        type="button"
        className="primary-button"
        disabled={credentialsSaving}
onClick={saveCredentials}
>        {credentialsSaving
          ? "Verifying..."
          : "Verify & Save"}
      </button>

    </div>

  </div>
)}
{deleteClusterTarget && (
  <div className="cluster-form-card">

    <div className="cluster-form-header">
      <div>
        <h3>Delete Cluster</h3>

        <p>
          This action will permanently delete{" "}
          <strong>{deleteClusterTarget.name}</strong>
          {" "}and its related monitoring data.
        </p>
      </div>

      <button
        type="button"
        onClick={() => {
          setDeleteClusterTarget(null);
          setDeleteClusterConfirm("");
          setDeleteClusterMessage("");
        }}
      >
        Cancel
      </button>
    </div>

    <div
      style={{
        marginBottom: "14px",
        padding: "12px",
        background: "#fef2f2",
        border: "1px solid #fecaca",
        borderRadius: "8px",
        color: "#991b1b",
        fontSize: "12px"
      }}
    >
      Warning: deleting this cluster also removes related
      nodes, Solr topology and stored monitoring data.
    </div>

    <div className="cluster-form-grid">

      <label>
        Type the cluster name to confirm

        <input
          type="text"
          placeholder={deleteClusterTarget.name}
          value={deleteClusterConfirm}
          onChange={(e) =>
            setDeleteClusterConfirm(
              e.target.value
            )
          }
        />
      </label>

    </div>

    {deleteClusterMessage && (
      <div
        style={{
          marginTop: "12px",
          padding: "10px 12px",
          background: "#fef2f2",
          border: "1px solid #fecaca",
          borderRadius: "8px",
          color: "#991b1b",
          fontSize: "12px"
        }}
      >
        {deleteClusterMessage}
      </div>
    )}

    <div className="cluster-form-actions">

      <button
        type="button"
        onClick={() => {
          setDeleteClusterTarget(null);
          setDeleteClusterConfirm("");
          setDeleteClusterMessage("");
        }}
      >
        Cancel
      </button>

      <button
        type="button"
        className="danger-action"
        disabled={
          deleteClusterSaving ||
          deleteClusterConfirm !==
            deleteClusterTarget.name
        }
onClick={deleteCluster}
      >
        {deleteClusterSaving
          ? "Deleting..."
          : "Delete Permanently"}
      </button>

    </div>

  </div>
)}
        <div className="cluster-management-grid">

          {clusters.length === 0 ? (
            <div className="empty-state">
              No clusters configured.
            </div>
          ) : (
clusters.map(cluster => (

              <div
                className="cluster-management-card"
                key={cluster.id}
              >

                <div className="cluster-card-header">

                  <div>
                    <h3>{cluster.name}</h3>

                    <span className="cluster-id">
                      Cluster ID: {cluster.id}
                    </span>
                  </div>

                  <span
                    className={
                      cluster.enabled
                        ? "cluster-status enabled"
                        : "cluster-status disabled"
                    }
                  >
                    {cluster.enabled ? "Enabled" : "Disabled"}
                  </span>

                </div>

                <div className="cluster-details">

                  <div>
                    <span>Environment</span>
                    <strong>
                      {cluster.environment || "N/A"}
                    </strong>
                  </div>

                  <div>
                    <span>Solr Endpoint</span>
                    <strong>
                      {cluster.solr_scheme || "http"}
                      ://
                      {cluster.solr_port || 8983}
                    </strong>
                  </div>

                  <div>
                    <span>ZooKeeper</span>
                    <strong>
                      {cluster.zk_connection_string || "N/A"}
                    </strong>
                  </div>

                  <div>
                    <span>ZooKeeper Chroot</span>
                    <strong>
                      {cluster.zk_chroot || "/solr"}
                    </strong>
                  </div>

                  <div>
                    <span>Discovery Interval</span>
                    <strong>
                      {cluster.discovery_interval || 60}s
                    </strong>
                  </div>

                  <div>
                    <span>Credentials</span>

                    <strong>
                      {
                        cluster.credentials_configured
                          ? "Configured"
                          : "Not configured"
                      }
                    </strong>
                  </div>

                </div>

<div className="cluster-actions">

<button
  type="button"
  className="secondary-action"
  onClick={() => {
    setEditingCluster(cluster);

    setEditClusterForm({
      name:
        cluster.name || "",

      environment:
        cluster.environment || "lab",

      zk_connection_string:
        cluster.zk_connection_string || "",

      zk_chroot:
        cluster.zk_chroot || "/solr",

      solr_scheme:
        cluster.solr_scheme || "http",

      solr_port:
        cluster.solr_port || 8983,

      discovery_interval:
        cluster.discovery_interval || 60
    });

    setEditClusterMessage("");
  }}
>
  Edit
</button>
  <button
    type="button"
    className="secondary-action"
    onClick={() => {
      setCredentialsCluster(cluster);

      setCredentialsForm({
        username:
          cluster.solr_username || "",
        password: ""
      });

      setCredentialsMessage("");
    }}
  >
    Credentials
  </button>

  <button
    type="button"
    className={
      cluster.enabled
        ? "warning-action"
        : "success-action"
    }
onClick={() =>
  toggleClusterEnabled(
    cluster
  )
}
  >
    {
      cluster.enabled
        ? "Disable"
        : "Enable"
    }
  </button>
<button
  type="button"
  className="danger-action"
  onClick={() => {
    setDeleteClusterTarget(cluster);
    setDeleteClusterConfirm("");
    setDeleteClusterMessage("");
  }}
>
  Delete
</button>
</div>
              </div>

            ))
          )}

        </div>

      </main>

    </div>
  );
}
  if (loading) {

    return (

      <div className="center-screen">
        Loading MonKeeper...
      </div>

    );

  }


  /*
  ==========================================================
  KPI Values
  ==========================================================
  */

  const requestRate =
    requestSummary
      ?.request_rate
      ?.rate_1m;


  const p95 =
    requestSummary
      ?.latency
      ?.max_p95_ms;


  const p99 =
    requestSummary
      ?.latency
      ?.max_p99_ms;


  const totalErrors =
    requestSummary
      ?.errors
      ?.total_errors ??
    0;


  const timeouts =
    requestSummary
      ?.errors
      ?.timeouts ??
    0;


  /*
  ==========================================================
  Render
  ==========================================================
  */

  return (

    <div className="app">


      {/* ====================================================
          Header
      ==================================================== */}

      <header className="header">

        <div>

          <div className="brand-row">

            <div className="brand-mark">
              M
            </div>

            <div>

              <h1>
                MonKeeper
              </h1>

              <p>
                SolrCloud & ZooKeeper Observability
              </p>

            </div>

          </div>

        </div>


        <div className="header-actions">
<button
  type="button"
  className={
    activeView === "dashboard"
      ? "nav-button active"
      : "nav-button"
  }
  onClick={
    () => setActiveView("dashboard")
  }
>
  Dashboard
</button>

<button
  type="button"
  className={
    activeView === "clusters"
      ? "nav-button active"
      : "nav-button"
  }
  onClick={
    () => setActiveView("clusters")
  }
>
  Manage Clusters
</button>
          <div className="refresh-info">

            <span>
              Auto Refresh
            </span>

            <strong>
              15 sec
            </strong>

          </div>


          <button
            type="button"
            className="refresh-button"
            onClick={
              () =>
                loadData(true)
            }
            disabled={
              refreshing
            }
          >

            {
              refreshing
                ? "Refreshing..."
                : "Refresh Now"
            }

          </button>


          <div
            className={
              overallHealthy
                ? "health-badge healthy-badge"
                : "health-badge unhealthy-badge"
            }
          >

            <span
              className={
                overallHealthy
                  ? "status-dot healthy"
                  : "status-dot unhealthy"
              }
            />

            {
              overallHealthy
                ? "HEALTHY"
                : "DEGRADED"
            }

          </div>

        </div>

      </header>

{primaryCluster &&
  primaryCluster.enabled === false && (
    <div className="monitoring-disabled-banner">
      <div>
        <strong>
          Monitoring Disabled
        </strong>

        <span>
          This cluster is currently disabled.
          Displayed metrics may be historical.
        </span>
      </div>

      <span className="monitoring-disabled-badge">
        DISABLED
      </span>
    </div>
  )}
      {/* ====================================================
          Errors
      ==================================================== */}

      {
        error && (

          <div className="error-box">
            {error}
          </div>

        )
      }


      {/* ====================================================
          Cluster Summary
      ==================================================== */}
<section className="cluster-selector-bar">

  <div className="cluster-selector-info">

    <span className="cluster-selector-label">
      Monitoring Cluster
    </span>

    <span className="cluster-selector-help">
      Select the SolrCloud environment to monitor
    </span>

  </div>

  <select
    className="cluster-selector"
    value={
      selectedClusterId ||
      ""
    }
    onChange={
      event =>
        setSelectedClusterId(
          Number(
            event.target.value
          )
        )
    }
  >

    {
      clusters.map(
        cluster => (

          <option
            key={
              cluster.id
            }
            value={
              cluster.id
            }
          >

            {cluster.name}
            {" — "}
            {
              (
                cluster.environment ||
                "unknown"
              ).toUpperCase()
            }

          </option>

        )
      )
    }

  </select>

</section>
      <section className="cluster-bar">

        <TopMetric
          label="Cluster"
          value={
            primaryCluster
              ?.name ||
            "N/A"
          }
        />

        <TopMetric
          label="Environment"
          value={
            primaryCluster
              ?.environment ||
            "N/A"
          }
        />
<TopMetric
  label="Monitoring Status"
  value={
    clusterFreshness.status
  }
/>

<TopMetric
  label="Last Metric"
  value={
    clusterFreshness.ageSeconds !== null
      ? `${clusterFreshness.ageSeconds} sec ago`
      : "N/A"
  }
/>
        <TopMetric
          label="Solr Nodes"
          value={
            `${
              solrNodes.filter(
                node =>
                  node.status ===
                  "UP"
              ).length
            } / ${
              solrNodes.length
            }`
          }
        />

        <TopMetric
          label="ZooKeeper"
          value={
            `${
              zkNodes.filter(
                node =>
                  node.status ===
                  "UP"
              ).length
            } / ${
              zkNodes.length
            }`
          }
        />

        <TopMetric
          label="Collections"
          value={
            solrSummary
              ?.collections ??
            "N/A"
          }
        />

        <TopMetric
          label="Shards"
          value={
            solrSummary
              ?.shards ??
            "N/A"
          }
        />

        <TopMetric
          label="Replicas"
          value={
            solrSummary
              ? `${
                  solrSummary
                    .active_replicas
                } / ${
                  solrSummary
                    .replicas
                }`
              : "N/A"
          }
        />

        <TopMetric
          label="Last Updated"
          value={
            lastUpdated
              ? lastUpdated
                  .toLocaleTimeString()
              : "N/A"
          }
        />

      </section>


      {/* ====================================================
          Request Performance
      ==================================================== */}

      <SectionTitle
        title="Request Performance"
        subtitle="Live Solr request, latency and error telemetry"
      />


      <div className="kpi-grid">

        <KpiCard
          label="Request Rate"
          value={
            `${
              fmt(
                requestRate,
                4
              )
            } req/s`
          }
          sub="1 minute rate"
        />

        <KpiCard
          label="P95 Latency"
          value={
            `${
              fmt(
                p95,
                2
              )
            } ms`
          }
          sub="Slowest active handler"
        />

        <KpiCard
          label="P99 Latency"
          value={
            `${
              fmt(
                p99,
                2
              )
            } ms`
          }
          sub="Tail latency"
        />

        <KpiCard
          label="Errors"
          value={
            totalErrors
          }
          sub={
            `${timeouts} timeouts`
          }
          alert={
            totalErrors > 0
          }
        />

        <KpiCard
          label="Active Handlers"
          value={
            requestSummary
              ?.active_handlers ??
            "N/A"
          }
          sub="QUERY / UPDATE"
        />

        <KpiCard
          label="Cumulative Requests"
          value={
            requestSummary
              ?.cumulative_requests ??
            "N/A"
          }
          sub="Current Solr counters"
        />

      </div>


      {
        requestSummary
          ?.slowest_handler &&
        (

          <div className="slow-handler">

            <div>

              <span className="eyebrow">
                Slowest Handler
              </span>

              <strong>

                {
                  requestSummary
                    .slowest_handler
                    .category
                }

                {
                  requestSummary
                    .slowest_handler
                    .handler
                }

              </strong>

            </div>


            <div>

              <span className="eyebrow">
                Core
              </span>

              <strong>
                {
                  requestSummary
                    .slowest_handler
                    .core_name
                }
              </strong>

            </div>


            <div>

              <span className="eyebrow">
                Node
              </span>

              <strong>
                {
                  requestSummary
                    .slowest_handler
                    .hostname
                }
              </strong>

            </div>


            <div>

              <span className="eyebrow">
                P95
              </span>

              <strong>

                {
                  fmt(
                    requestSummary
                      .slowest_handler
                      .p95_ms,
                    2
                  )
                } ms

              </strong>

            </div>

          </div>

        )
      }


      <div className="chart-grid">

        <ChartCard
          title="Request Rate"
          subtitle="Last 60 minutes"
        >

          <Line
            data={
              requestRateChartData
            }
            options={
              chartOptions
            }
          />

        </ChartCard>


        <ChartCard
          title="P95 / P99 Latency"
          subtitle="Last 60 minutes"
        >

          <Line
            data={
              latencyChartData
            }
            options={
              chartOptions
            }
          />

        </ChartCard>

      </div>


      {/* ====================================================
          Solr Nodes
      ==================================================== */}

      <SectionTitle
        title="Solr Nodes"
        subtitle="JVM and operating system telemetry"
      />


      <div className="cards">

        {
          currentMetrics.map(
            (
              metric,
              index
            ) => {

              const nodeColor =
                getNodeColor(
                  metric.hostname,
                  index
                );


              return (

                <div
                  className="card"
                  key={
                    metric.node_id
                  }
                  style={{
                    borderTop:
                      `3px solid ${nodeColor}`
                  }}
                >

                  <div className="card-title">

                    <div>

                      <h3
                        style={{
                          color:
                            nodeColor
                        }}
                      >
                        {
                          metric.hostname
                        }
                      </h3>

                      <span>
                        {
                          metric.ip_address
                        }
                      </span>

                    </div>


                    <span className="pill up">
                      UP
                    </span>

                  </div>


                  <MetricRow
                    label="Heap Usage"
                    value={
                      `${
                        fmt(
                          metric
                            .heap_usage_percent,
                          1
                        )
                      }%`
                    }
                  />

                  <MetricRow
                    label="Heap Used"
                    value={
                      `${
                        fmt(
                          metric
                            .heap_used_mb,
                          1
                        )
                      } / ${
                        fmt(
                          metric
                            .heap_max_mb,
                          0
                        )
                      } MB`
                    }
                  />

                  <MetricRow
                    label="Process CPU"
                    value={
                      `${
                        fmt(
                          metric
                            .process_cpu_percent,
                          1
                        )
                      }%`
                    }
                  />

                  <MetricRow
                    label="System CPU"
                    value={
                      `${
                        fmt(
                          metric
                            .system_cpu_percent,
                          1
                        )
                      }%`
                    }
                  />

                  <MetricRow
                    label="RAM Free"
                    value={
                      `${
                        fmt(
                          safeNumber(
                            metric
                              .ram_free_mb
                          ) /
                          1024,
                          2
                        )
                      } GB`
                    }
                  />

                  <MetricRow
                    label="Threads"
                    value={
                      metric
                        .thread_count
                    }
                  />

                  <MetricRow
                    label="Young GC"
                    value={
                      metric
                        .young_gc_count
                    }
                  />

                  <MetricRow
                    label="Old GC"
                    value={
                      metric
                        .old_gc_count
                    }
                  />

                  <MetricRow
                    label="Deadlocks"
                    value={
                      metric
                        .deadlock_count
                    }
                  />

                  <MetricRow
                    label="Open FD"
                    value={
                      metric
                        .open_file_descriptors
                    }
                  />

                </div>

              );

            }
          )
        }

      </div>


      {/* ====================================================
          JVM Charts
      ==================================================== */}

      <div className="chart-grid">

        <ChartCard
          title="Heap Usage"
          subtitle="Last 60 minutes"
        >

          <Line
            data={
              heapChartData
            }
            options={
              chartOptions
            }
          />

        </ChartCard>


        <ChartCard
          title="Process CPU"
          subtitle="Last 60 minutes"
        >

          <Line
            data={
              cpuChartData
            }
            options={
              chartOptions
            }
          />

        </ChartCard>

      </div>


      {/* ====================================================
          SolrCloud
      ==================================================== */}

      <SectionTitle
        title="SolrCloud"
        subtitle="Topology and replica consistency"
      />


      <div className="two-column">

        <div className="card">

          <div className="card-title">

            <div>

              <h3>
                Topology
              </h3>

              <span>
                Collections, shards and replicas
              </span>

            </div>

          </div>


          <TopologyView
            topology={
              topology
            }
          />

        </div>


        <div className="card">

          <div className="card-title">

            <div>

              <h3>
                Replica Consistency
              </h3>

              <span>
                Document count validation
              </span>

            </div>

          </div>


          <ConsistencyView
            consistency={
              consistency
            }
          />

        </div>

      </div>


      {/* ====================================================
          ZooKeeper
      ==================================================== */}

      <SectionTitle
        title="ZooKeeper Ensemble"
        subtitle="Current ensemble membership and roles"
      />


      <div className="cards">

        {
          zkNodes.map(
            node => (

              <div
                className="card compact"
                key={
                  node.id
                }
              >

                <div className="card-title">

                  <div>

                    <h3>
                      {
                        node.hostname
                      }
                    </h3>

                    <span>

                      {
                        node.ip_address ||
                        node.hostname
                      }

                      :

                      {
                        node.port
                      }

                    </span>

                  </div>


                  <span
                    className={
                      node.status ===
                      "UP"
                        ? "pill up"
                        : "pill down"
                    }
                  >
                    {
                      node.status
                    }
                  </span>

                </div>


                <MetricRow
                  label="Role"
                  value={
                    (
                      node.role ||
                      "unknown"
                    ).toUpperCase()
                  }
                />

                <MetricRow
                  label="Address"
                  value={
                    node.ip_address ||
                    node.hostname
                  }
                />

                <MetricRow
                  label="Client Port"
                  value={
                    node.port
                  }
                />

              </div>

            )
          )
        }

      </div>


      {/* ====================================================
          SPL Footer
      ==================================================== */}

      <footer className="footer spl-footer">

        <div className="spl-footer-left">

          <a
            href="https://splonline.com.sa"
            target="_blank"
            rel="noreferrer"
            className="spl-logo-link"
          >

            <img
              src="/spllogo.png"
              alt="SPL Logo"
              className="spl-footer-logo"
            />

          </a>


          <div className="spl-footer-divider" />


          <div className="spl-footer-unit">

            <strong
              className="spl-footer-ar"
              dir="rtl"
            >
              وحدة البرمجيات الحكومية مفتوحة المصدر
            </strong>

            <span className="spl-footer-en">
              Government Open Source Software Unit
            </span>

            <a
              href="https://splonline.com.sa"
              target="_blank"
              rel="noreferrer"
              className="spl-footer-link"
            >
              splonline.com.sa
            </a>

          </div>

        </div>


        <div className="spl-footer-right">

          <strong>
            MonKeeper
          </strong>

          <span>
            SolrCloud & ZooKeeper Observability
          </span>

          <span>
            Saudi Post | SPL
          </span>

        </div>

      </footer>

    </div>

  );

}


/*
============================================================
Small Components
============================================================
*/

function TopMetric({
  label,
  value
}) {

  return (

    <div className="top-metric">

      <span className="label">
        {label}
      </span>

      <strong>
        {value}
      </strong>

    </div>

  );

}


function SectionTitle({
  title,
  subtitle
}) {

  return (

    <div className="section-heading">

      <div>

        <h2>
          {title}
        </h2>

        {
          subtitle &&
          (
            <p>
              {subtitle}
            </p>
          )
        }

      </div>

    </div>

  );

}


function KpiCard({
  label,
  value,
  sub,
  alert = false
}) {

  return (

    <div
      className={
        alert
          ? "kpi-card alert"
          : "kpi-card"
      }
    >

      <span className="kpi-label">
        {label}
      </span>

      <strong className="kpi-value">
        {value}
      </strong>

      <span className="kpi-sub">
        {sub}
      </span>

    </div>

  );

}


function ChartCard({
  title,
  subtitle,
  children
}) {

  return (

    <div className="chart-card">

      <div className="chart-header">

        <div>

          <h3>
            {title}
          </h3>

          <span>
            {subtitle}
          </span>

        </div>

      </div>

      <div className="chart-body">
        {children}
      </div>

    </div>

  );

}


function MetricRow({
  label,
  value
}) {

  return (

    <div className="metric-row">

      <span>
        {label}
      </span>

      <strong>

        {
          value === null ||
          value === undefined
            ? "N/A"
            : value
        }

      </strong>

    </div>

  );

}


/*
============================================================
Topology
============================================================
*/

function TopologyView({
  topology
}) {

  if (!topology) {

    return (

      <div className="empty-state">
        Topology data unavailable
      </div>

    );

  }


  const collections =
    topology.collections ||
    topology.topology ||
    [];


  if (
    !Array.isArray(
      collections
    )
  ) {

    return (

      <pre className="json-preview">

        {
          JSON.stringify(
            topology,
            null,
            2
          )
        }

      </pre>

    );

  }


  if (
    collections.length ===
    0
  ) {

    return (

      <div className="empty-state">
        No topology records
      </div>

    );

  }


  return (

    <div className="topology-list">

      {
        collections.map(
          (
            collection,
            index
          ) => (

            <div
              className="topology-collection"
              key={
                collection.name ||
                index
              }
            >

              <div className="collection-name">

                {
                  collection.name ||
                  collection.collection ||
                  "Collection"
                }

              </div>


              {
                (
                  collection.shards ||
                  []
                ).map(
                  (
                    shard,
                    shardIndex
                  ) => (

                    <div
                      className="shard-block"
                      key={
                        shard.name ||
                        shard.shard ||
                        shardIndex
                      }
                    >

                      <div className="shard-name">

                        {
                          shard.name ||
                          shard.shard
                        }

                      </div>


                      <div className="replica-list">

                        {
                          (
                            shard.replicas ||
                            []
                          ).map(
                            (
                              replica,
                              replicaIndex
                            ) => (

                              <div
                                className="replica-row"
                                key={
                                  replica.core_name ||
                                  replicaIndex
                                }
                              >

                                <div>

                                  <strong>
                                    {
                                      replica.hostname ||
                                      "unknown"
                                    }
                                  </strong>

                                  <span>
                                    {
                                      replica.core_name ||
                                      replica.replica_name
                                    }
                                  </span>

                                </div>


                                <span
                                  className={
                                    replica.is_leader
                                      ? "role leader"
                                      : "role follower"
                                  }
                                >

                                  {
                                    replica.is_leader
                                      ? "LEADER"
                                      : "REPLICA"
                                  }

                                </span>

                              </div>

                            )
                          )
                        }

                      </div>

                    </div>

                  )
                )
              }

            </div>

          )
        )
      }

    </div>

  );

}


/*
============================================================
Consistency
============================================================
*/

function ConsistencyView({
  consistency
}) {

  if (!consistency) {

    return (

      <div className="empty-state">
        Consistency data unavailable
      </div>

    );

  }


  const shards =
    consistency.shards ||
    consistency.results ||
    consistency.consistency ||
    [];


  if (
    !Array.isArray(
      shards
    )
  ) {

    return (

      <div className="consistency-summary">

        <MetricRow
          label="Consistent Shards"
          value={
            consistency
              .consistent_shards ??
            "N/A"
          }
        />

        <MetricRow
          label="Mismatch Shards"
          value={
            consistency
              .mismatch_shards ??
            "N/A"
          }
        />

        <MetricRow
          label="Unknown Shards"
          value={
            consistency
              .unknown_shards ??
            "N/A"
          }
        />

      </div>

    );

  }


  if (
    shards.length ===
    0
  ) {

    return (

      <div className="empty-state">
        No consistency records
      </div>

    );

  }


  return (

    <div className="consistency-list">

      {
        shards.map(
          (
            item,
            index
          ) => {

            const status =
              item.status ||
              item.consistency_status ||
              (
                item.consistent
                  ? "CONSISTENT"
                  : "UNKNOWN"
              );


            return (

              <div
                className="consistency-row"
                key={
                  `${
                    item.collection ||
                    ""
                  }-${
                    item.shard ||
                    index
                  }`
                }
              >

                <div>

                  <strong>

                    {
                      item.collection
                        ? `${
                            item.collection
                          } / `
                        : ""
                    }

                    {
                      item.shard ||
                      item.shard_name ||
                      `Shard ${
                        index + 1
                      }`
                    }

                  </strong>


                  <span>

                    {
                      item.doc_count !==
                      undefined
                        ? `${
                            item.doc_count
                          } documents`
                        : "Replica document validation"
                    }

                  </span>

                </div>


                <span
                  className={
                    String(
                      status
                    )
                      .toUpperCase()
                      .includes(
                        "CONSIST"
                      )
                      ? "role leader"
                      : "role warning"
                  }
                >

                  {status}

                </span>

              </div>

            );

          }
        )
      }

    </div>

  );

}


/*
============================================================
React
============================================================
*/

ReactDOM
  .createRoot(
    document.getElementById(
      "root"
    )
  )
  .render(

    <React.StrictMode>

      <App />

    </React.StrictMode>

  );
