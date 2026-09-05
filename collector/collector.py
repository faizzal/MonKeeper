import os
import time
from datetime import datetime, timezone

import psycopg
import requests


API_URL = os.getenv(
    "MONKEEPER_API_URL",
    "http://api:8000"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

POLL_INTERVAL = int(
    os.getenv(
        "COLLECTOR_POLL_INTERVAL",
        "5"
    )
)

METRICS_INTERVAL = int(
    os.getenv(
        "METRICS_INTERVAL",
        "15"
    )
)

TOPOLOGY_INTERVAL = int(
    os.getenv(
        "TOPOLOGY_INTERVAL",
        "60"
    )
)

REPLICA_METRICS_INTERVAL = int(
    os.getenv(
        "REPLICA_METRICS_INTERVAL",
        "60"
    )
)
REQUEST_METRICS_INTERVAL = int(
    os.getenv(
        "REQUEST_METRICS_INTERVAL",
        "60"
    )
)

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured"
    )


# ============================================================
# Logging
# ============================================================

def log(message):
    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    print(
        f"{timestamp} | {message}",
        flush=True
    )


# ============================================================
# API helpers
# ============================================================

def get_clusters():
    response = requests.get(
        f"{API_URL}/clusters",
        timeout=10
    )

    response.raise_for_status()

    return response.json().get(
        "clusters",
        []
    )


def get_nodes():
    response = requests.get(
        f"{API_URL}/nodes",
        timeout=10
    )

    response.raise_for_status()

    return response.json().get(
        "nodes",
        []
    )


def get_credentials(cluster_id):
    response = requests.get(
        f"{API_URL}/internal/clusters/"
        f"{cluster_id}/credentials",
        timeout=10
    )

    response.raise_for_status()

    return response.json()


def run_discovery(cluster_id):
    response = requests.get(
        f"{API_URL}/discovery/test/"
        f"{cluster_id}",
        timeout=30
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# Helpers
# ============================================================

def bytes_to_mb(value):
    if value is None:
        return None

    return value / 1024 / 1024


def percent(value):
    if value is None:
        return None

    return value * 100


def format_number(
    value,
    decimals=1
):
    if value is None:
        return "N/A"

    return f"{value:.{decimals}f}"


def parse_hostname_from_node_name(
    node_name
):
    if not node_name:
        return None

    value = node_name

    if value.endswith("_solr"):
        value = value[:-5]

    if ":" in value:
        value = value.rsplit(
            ":",
            1
        )[0]

    return value


def get_solr_target_node(
    cluster_id,
    nodes
):
    solr_nodes = [
        node
        for node in nodes
        if (
            node.get("cluster_id")
            == cluster_id

            and node.get("node_type")
            == "solr"

            and node.get("status")
            == "UP"
        )
    ]

    if not solr_nodes:
        return None

    return solr_nodes[0]


# ============================================================
# JVM metrics
# ============================================================

def collect_solr_jvm(
    node,
    username,
    password,
    scheme="http"
):
    hostname = node.get(
        "hostname"
    )

    target = (
        node.get("ip_address")
        or hostname
    )

    port = (
        node.get("port")
        or 8983
    )

    url = (
        f"{scheme}://{target}:{port}"
        "/solr/admin/metrics"
        "?group=jvm&wt=json"
    )

    response = requests.get(
        url,
        auth=(
            username,
            password
        ),
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    metrics = (
        data
        .get("metrics", {})
        .get("solr.jvm", {})
    )

    return {
        "hostname": hostname,
        "ip_address": node.get(
            "ip_address"
        ),
        "port": port,

        "heap_used": metrics.get(
            "memory.heap.used"
        ),

        "heap_max": metrics.get(
            "memory.heap.max"
        ),

        "heap_usage": metrics.get(
            "memory.heap.usage"
        ),

        "young_gc_count": metrics.get(
            "gc.G1-Young-Generation.count"
        ),

        "young_gc_time": metrics.get(
            "gc.G1-Young-Generation.time"
        ),

        "old_gc_count": metrics.get(
            "gc.G1-Old-Generation.count"
        ),

        "old_gc_time": metrics.get(
            "gc.G1-Old-Generation.time"
        ),

        "process_cpu_load": metrics.get(
            "os.processCpuLoad"
        ),

        "system_cpu_load": metrics.get(
            "os.systemCpuLoad"
        ),

        "thread_count": metrics.get(
            "threads.count"
        ),

        "deadlock_count": metrics.get(
            "threads.deadlock.count"
        ),

        "physical_memory_total": metrics.get(
            "os.totalPhysicalMemorySize"
        ),

        "physical_memory_free": metrics.get(
            "os.freePhysicalMemorySize"
        ),

        "open_file_descriptors": metrics.get(
            "os.openFileDescriptorCount"
        )
    }


def save_solr_metric(
    cluster_id,
    node_id,
    metric
):
    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO solr_metrics (
                    cluster_id,
                    node_id,
                    heap_used_mb,
                    heap_max_mb,
                    heap_usage_percent,
                    young_gc_count,
                    young_gc_time_ms,
                    old_gc_count,
                    old_gc_time_ms,
                    process_cpu_percent,
                    system_cpu_percent,
                    thread_count,
                    deadlock_count,
                    ram_total_mb,
                    ram_free_mb,
                    open_file_descriptors
                )
                VALUES (
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s
                )
                """,
                (
                    cluster_id,
                    node_id,

                    bytes_to_mb(
                        metric["heap_used"]
                    ),

                    bytes_to_mb(
                        metric["heap_max"]
                    ),

                    percent(
                        metric["heap_usage"]
                    ),

                    metric[
                        "young_gc_count"
                    ],

                    metric[
                        "young_gc_time"
                    ],

                    metric[
                        "old_gc_count"
                    ],

                    metric[
                        "old_gc_time"
                    ],

                    percent(
                        metric[
                            "process_cpu_load"
                        ]
                    ),

                    percent(
                        metric[
                            "system_cpu_load"
                        ]
                    ),

                    metric[
                        "thread_count"
                    ],

                    metric[
                        "deadlock_count"
                    ],

                    bytes_to_mb(
                        metric[
                            "physical_memory_total"
                        ]
                    ),

                    bytes_to_mb(
                        metric[
                            "physical_memory_free"
                        ]
                    ),

                    metric[
                        "open_file_descriptors"
                    ]
                )
            )

        conn.commit()


def collect_cluster_metrics(
    cluster,
    nodes
):
    cluster_id = cluster["id"]

    try:
        credentials = get_credentials(
            cluster_id
        )

        username = credentials[
            "username"
        ]

        password = credentials[
            "password"
        ]

    except Exception as exc:
        log(
            f"Cluster {cluster_id} | "
            f"Credentials unavailable | "
            f"{exc}"
        )

        return

    solr_nodes = [
        node
        for node in nodes
        if (
            node.get("cluster_id")
            == cluster_id

            and node.get("node_type")
            == "solr"

            and node.get("status")
            == "UP"
        )
    ]

    scheme = (
        cluster.get(
            "solr_scheme"
        )
        or "http"
    )

    for node in solr_nodes:

        try:
            metric = collect_solr_jvm(
                node,
                username,
                password,
                scheme
            )

            save_solr_metric(
                cluster_id,
                node["id"],
                metric
            )

            log(
                f"JVM "
                f"{metric['hostname']} | "
                f"IP={metric['ip_address']} | "
                f"Heap="
                f"{format_number(bytes_to_mb(metric['heap_used']))}/"
                f"{format_number(bytes_to_mb(metric['heap_max']))} MB | "
                f"Usage="
                f"{format_number(percent(metric['heap_usage']))}% | "
                f"YoungGC="
                f"{metric['young_gc_count']} | "
                f"OldGC="
                f"{metric['old_gc_count']} | "
                f"ProcessCPU="
                f"{format_number(percent(metric['process_cpu_load']))}% | "
                f"SystemCPU="
                f"{format_number(percent(metric['system_cpu_load']))}% | "
                f"Threads="
                f"{metric['thread_count']} | "
                f"Deadlocks="
                f"{metric['deadlock_count']} | "
                f"RAMFree="
                f"{format_number(bytes_to_mb(metric['physical_memory_free']))}/"
                f"{format_number(bytes_to_mb(metric['physical_memory_total']))} MB | "
                f"OpenFD="
                f"{metric['open_file_descriptors']} | "
                f"DB=stored"
            )

        except Exception as exc:

            log(
                f"JVM metrics error for "
                f"{node.get('hostname')} | "
                f"{exc}"
            )


# ============================================================
# Solr topology
# ============================================================

def collect_solr_topology(
    node,
    username,
    password,
    scheme="http"
):
    target = (
        node.get("ip_address")
        or node.get("hostname")
    )

    port = (
        node.get("port")
        or 8983
    )

    url = (
        f"{scheme}://{target}:{port}"
        "/solr/admin/collections"
        "?action=CLUSTERSTATUS&wt=json"
    )

    response = requests.get(
        url,
        auth=(
            username,
            password
        ),
        timeout=20
    )

    response.raise_for_status()

    return response.json()


def sync_solr_topology(
    cluster_id,
    topology
):
    cluster_data = topology.get(
        "cluster",
        {}
    )

    collections = cluster_data.get(
        "collections",
        {}
    )

    now = datetime.now(
        timezone.utc
    )

    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        with conn.cursor() as cur:

            for (
                collection_name,
                collection_data
            ) in collections.items():

                cur.execute(
                    """
                    INSERT INTO solr_collections (
                        cluster_id,
                        name,
                        config_name,
                        replication_factor,
                        nrt_replicas,
                        tlog_replicas,
                        pull_replicas,
                        router_name,
                        health,
                        creation_time_ms,
                        znode_version,
                        last_seen,
                        updated_at
                    )
                    VALUES (
                        %s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s
                    )
                    ON CONFLICT (
                        cluster_id,
                        name
                    )
                    DO UPDATE SET
                        config_name =
                            EXCLUDED.config_name,
                        replication_factor =
                            EXCLUDED.replication_factor,
                        nrt_replicas =
                            EXCLUDED.nrt_replicas,
                        tlog_replicas =
                            EXCLUDED.tlog_replicas,
                        pull_replicas =
                            EXCLUDED.pull_replicas,
                        router_name =
                            EXCLUDED.router_name,
                        health =
                            EXCLUDED.health,
                        creation_time_ms =
                            EXCLUDED.creation_time_ms,
                        znode_version =
                            EXCLUDED.znode_version,
                        last_seen =
                            EXCLUDED.last_seen,
                        updated_at =
                            EXCLUDED.updated_at
                    RETURNING id
                    """,
                    (
                        cluster_id,
                        collection_name,

                        collection_data.get(
                            "configName"
                        ),

                        collection_data.get(
                            "replicationFactor"
                        ),

                        int(
                            collection_data.get(
                                "nrtReplicas",
                                0
                            )
                            or 0
                        ),

                        int(
                            collection_data.get(
                                "tlogReplicas",
                                0
                            )
                            or 0
                        ),

                        int(
                            collection_data.get(
                                "pullReplicas",
                                0
                            )
                            or 0
                        ),

                        collection_data.get(
                            "router",
                            {}
                        ).get(
                            "name"
                        ),

                        collection_data.get(
                            "health"
                        ),

                        collection_data.get(
                            "creationTimeMillis"
                        ),

                        collection_data.get(
                            "znodeVersion"
                        ),

                        now,
                        now
                    )
                )

                collection_id = (
                    cur.fetchone()[0]
                )

                shards = (
                    collection_data.get(
                        "shards",
                        {}
                    )
                )

                for (
                    shard_name,
                    shard_data
                ) in shards.items():

                    cur.execute(
                        """
                        INSERT INTO solr_shards (
                            collection_id,
                            name,
                            hash_range,
                            state,
                            health,
                            last_seen,
                            updated_at
                        )
                        VALUES (
                            %s,%s,%s,%s,%s,%s,%s
                        )
                        ON CONFLICT (
                            collection_id,
                            name
                        )
                        DO UPDATE SET
                            hash_range =
                                EXCLUDED.hash_range,
                            state =
                                EXCLUDED.state,
                            health =
                                EXCLUDED.health,
                            last_seen =
                                EXCLUDED.last_seen,
                            updated_at =
                                EXCLUDED.updated_at
                        RETURNING id
                        """,
                        (
                            collection_id,
                            shard_name,

                            shard_data.get(
                                "range"
                            ),

                            shard_data.get(
                                "state"
                            ),

                            shard_data.get(
                                "health"
                            ),

                            now,
                            now
                        )
                    )

                    shard_id = (
                        cur.fetchone()[0]
                    )

                    replicas = (
                        shard_data.get(
                            "replicas",
                            {}
                        )
                    )

                    for (
                        replica_name,
                        replica_data
                    ) in replicas.items():

                        node_name = (
                            replica_data.get(
                                "node_name"
                            )
                        )

                        hostname = (
                            parse_hostname_from_node_name(
                                node_name
                            )
                        )

                        is_leader = (
                            str(
                                replica_data.get(
                                    "leader"
                                )
                            ).lower()
                            == "true"
                        )

                        cur.execute(
                            """
                            INSERT INTO solr_replicas (
                                shard_id,
                                replica_name,
                                core_name,
                                node_name,
                                hostname,
                                base_url,
                                replica_type,
                                state,
                                is_leader,
                                last_seen,
                                updated_at
                            )
                            VALUES (
                                %s,%s,%s,%s,%s,
                                %s,%s,%s,%s,%s,%s
                            )
                            ON CONFLICT (
                                shard_id,
                                replica_name
                            )
                            DO UPDATE SET
                                core_name =
                                    EXCLUDED.core_name,
                                node_name =
                                    EXCLUDED.node_name,
                                hostname =
                                    EXCLUDED.hostname,
                                base_url =
                                    EXCLUDED.base_url,
                                replica_type =
                                    EXCLUDED.replica_type,
                                state =
                                    EXCLUDED.state,
                                is_leader =
                                    EXCLUDED.is_leader,
                                last_seen =
                                    EXCLUDED.last_seen,
                                updated_at =
                                    EXCLUDED.updated_at
                            """,
                            (
                                shard_id,
                                replica_name,

                                replica_data.get(
                                    "core"
                                ),

                                node_name,
                                hostname,

                                replica_data.get(
                                    "base_url"
                                ),

                                replica_data.get(
                                    "type"
                                ),

                                replica_data.get(
                                    "state"
                                ),

                                is_leader,

                                now,
                                now
                            )
                        )

        conn.commit()


def collect_cluster_topology(
    cluster,
    nodes
):
    cluster_id = cluster["id"]

    try:
        credentials = get_credentials(
            cluster_id
        )

        username = credentials[
            "username"
        ]

        password = credentials[
            "password"
        ]

    except Exception as exc:

        log(
            f"Topology credentials unavailable "
            f"for cluster {cluster_id} | "
            f"{exc}"
        )

        return

    node = get_solr_target_node(
        cluster_id,
        nodes
    )

    if not node:
        log(
            f"Cluster {cluster_id} | "
            "No Solr node available "
            "for topology collection"
        )

        return

    scheme = (
        cluster.get(
            "solr_scheme"
        )
        or "http"
    )

    try:
        topology = collect_solr_topology(
            node,
            username,
            password,
            scheme
        )

        sync_solr_topology(
            cluster_id,
            topology
        )

        collections = (
            topology
            .get("cluster", {})
            .get("collections", {})
        )

        collection_count = len(
            collections
        )

        shard_count = 0
        replica_count = 0

        for collection_data in (
            collections.values()
        ):

            shards = (
                collection_data.get(
                    "shards",
                    {}
                )
            )

            shard_count += len(
                shards
            )

            for shard_data in (
                shards.values()
            ):

                replica_count += len(
                    shard_data.get(
                        "replicas",
                        {}
                    )
                )

        log(
            f"Topology cluster "
            f"{cluster_id} | "
            f"Collections="
            f"{collection_count} | "
            f"Shards="
            f"{shard_count} | "
            f"Replicas="
            f"{replica_count} | "
            f"DB=synced"
        )

    except Exception as exc:

        log(
            f"Topology error "
            f"for cluster "
            f"{cluster_id} | "
            f"{exc}"
        )


# ============================================================
# Replica document metrics
# ============================================================

def get_cluster_replicas(
    cluster_id
):
    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    r.id,
                    r.core_name,
                    r.hostname,
                    r.state,
                    r.is_leader,
                    s.name,
                    c.name
                FROM solr_replicas r
                JOIN solr_shards s
                  ON s.id = r.shard_id
                JOIN solr_collections c
                  ON c.id = s.collection_id
                WHERE c.cluster_id = %s
                ORDER BY
                    c.name,
                    s.name,
                    r.hostname
                """,
                (
                    cluster_id,
                )
            )

            rows = cur.fetchall()

    return [
        {
            "replica_id": row[0],
            "core_name": row[1],
            "hostname": row[2],
            "state": row[3],
            "is_leader": row[4],
            "shard_name": row[5],
            "collection_name": row[6]
        }
        for row in rows
    ]


def get_node_address(
    cluster_id,
    hostname,
    nodes
):
    for node in nodes:

        if (
            node.get("cluster_id")
            == cluster_id

            and node.get("node_type")
            == "solr"

            and node.get("hostname")
            == hostname
        ):

            return (
                node.get("ip_address")
                or node.get("hostname")
            ), (
                node.get("port")
                or 8983
            )

    return None, None


def collect_replica_doc_count(
    target,
    port,
    core_name,
    username,
    password,
    scheme="http"
):
    url = (
        f"{scheme}://{target}:{port}"
        f"/solr/{core_name}/select"
    )

    started = time.perf_counter()

    response = requests.get(
        url,
        params={
            "q": "*:*",
            "rows": 0,
            "distrib": "false",
            "wt": "json"
        },
        auth=(
            username,
            password
        ),
        timeout=20
    )

    elapsed_ms = (
        time.perf_counter()
        - started
    ) * 1000

    response.raise_for_status()

    data = response.json()

    doc_count = (
        data
        .get("response", {})
        .get("numFound")
    )

    qtime = (
        data
        .get("responseHeader", {})
        .get("QTime")
    )

    return {
        "doc_count": doc_count,
        "query_time_ms": (
            qtime
            if qtime is not None
            else elapsed_ms
        )
    }


def save_replica_metric(
    replica_id,
    doc_count,
    query_time_ms,
    status
):
    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO solr_replica_metrics (
                    replica_id,
                    doc_count,
                    query_time_ms,
                    collection_status
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    replica_id,
                    doc_count,
                    query_time_ms,
                    status
                )
            )

        conn.commit()


def collect_replica_metrics(
    cluster,
    nodes
):
    cluster_id = cluster[
        "id"
    ]

    try:
        credentials = get_credentials(
            cluster_id
        )

        username = credentials[
            "username"
        ]

        password = credentials[
            "password"
        ]

    except Exception as exc:

        log(
            f"Replica credentials unavailable "
            f"for cluster {cluster_id} | "
            f"{exc}"
        )

        return

    replicas = get_cluster_replicas(
        cluster_id
    )

    scheme = (
        cluster.get(
            "solr_scheme"
        )
        or "http"
    )

    for replica in replicas:

        target, port = get_node_address(
            cluster_id,
            replica["hostname"],
            nodes
        )

        if not target:

            log(
                f"Replica "
                f"{replica['core_name']} | "
                f"node address unavailable"
            )

            continue

        try:
            result = (
                collect_replica_doc_count(
                    target,
                    port,
                    replica["core_name"],
                    username,
                    password,
                    scheme
                )
            )

            save_replica_metric(
                replica[
                    "replica_id"
                ],
                result[
                    "doc_count"
                ],
                result[
                    "query_time_ms"
                ],
                "OK"
            )

            log(
                f"Replica "
                f"{replica['collection_name']}/"
                f"{replica['shard_name']} | "
                f"{replica['core_name']} | "
                f"Node="
                f"{replica['hostname']} | "
                f"Docs="
                f"{result['doc_count']} | "
                f"QTime="
                f"{result['query_time_ms']} ms | "
                f"Leader="
                f"{replica['is_leader']} | "
                f"DB=stored"
            )

        except Exception as exc:

            save_replica_metric(
                replica[
                    "replica_id"
                ],
                None,
                None,
                "ERROR"
            )

            log(
                f"Replica metrics error | "
                f"{replica['core_name']} | "
                f"{exc}"
            )

# ============================================================
# Solr Request / Error / Latency Metrics
# ============================================================

def collect_core_request_metrics(
    target,
    port,
    core_name,
    username,
    password,
    scheme="http"
):
    url = (
        f"{scheme}://{target}:{port}"
        "/solr/admin/metrics"
    )

    response = requests.get(
        url,
        params={
            "group": "core",
            "wt": "json"
        },
        auth=(
            username,
            password
        ),
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    registries = data.get(
        "metrics",
        {}
    )

    matching_registries = []

    for registry_name, metrics in registries.items():
        if not registry_name.startswith(
            "solr.core."
        ):
            continue

        normalized_registry = (
            registry_name[
                len("solr.core.") :
            ]
            .replace(
                ".shard",
                "_shard"
            )
            .replace(
                ".replica_",
                "_replica_"
            )
        )

        if normalized_registry == core_name:
            matching_registries.append(
                (
                    registry_name,
                    metrics
                )
            )

    results = []

    for registry_name, metrics in matching_registries:

        for metric_name, request_times in metrics.items():

            if not metric_name.endswith(
                ".requestTimes"
            ):
                continue

            try:
                category, remainder = metric_name.split(
                    ".",
                    1
                )
            except ValueError:
                continue

            if category not in (
                "QUERY",
                "UPDATE"
            ):
                continue

            handler = remainder[
                :-len(".requestTimes")
            ]

            prefix = (
                f"{category}.{handler}"
            )

            def metric_count(suffix):
                value = metrics.get(
                    f"{prefix}.{suffix}"
                )

                if isinstance(
                    value,
                    dict
                ):
                    return value.get(
                        "count",
                        0
                    )

                if isinstance(
                    value,
                    (int, float)
                ):
                    return value

                return 0

            if not isinstance(
                request_times,
                dict
            ):
                continue

            request_count = request_times.get(
                "count"
            )

            if request_count is None:
                request_count = metric_count(
                    "requests"
                )

            client_errors = metric_count(
                "clientErrors"
            )

            server_errors = metric_count(
                "serverErrors"
            )

            errors = metric_count(
                "errors"
            )

            timeouts = metric_count(
                "timeouts"
            )

            # Skip completely idle handlers.
            if (
                (request_count or 0) == 0
                and client_errors == 0
                and server_errors == 0
                and errors == 0
                and timeouts == 0
            ):
                continue

            results.append(
                {
                    "category": category,
                    "handler": handler,
                    "request_count": request_count,

                    "mean_rate": request_times.get(
                        "meanRate"
                    ),
                    "rate_1m": request_times.get(
                        "1minRate"
                    ),
                    "rate_5m": request_times.get(
                        "5minRate"
                    ),
                    "rate_15m": request_times.get(
                        "15minRate"
                    ),

                    "min_ms": request_times.get(
                        "min_ms"
                    ),
                    "max_ms": request_times.get(
                        "max_ms"
                    ),
                    "mean_ms": request_times.get(
                        "mean_ms"
                    ),
                    "median_ms": request_times.get(
                        "median_ms"
                    ),
                    "p75_ms": request_times.get(
                        "p75_ms"
                    ),
                    "p95_ms": request_times.get(
                        "p95_ms"
                    ),
                    "p99_ms": request_times.get(
                        "p99_ms"
                    ),
                    "p999_ms": request_times.get(
                        "p999_ms"
                    ),

                    "client_errors": client_errors,
                    "server_errors": server_errors,
                    "errors": errors,
                    "timeouts": timeouts
                }
            )

    return results

def save_request_metric(
    replica_id,
    metric
):
    with psycopg.connect(
        DATABASE_URL
    ) as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO solr_request_metrics (
                    replica_id,
                    category,
                    handler,
                    request_count,

                    mean_rate,
                    rate_1m,
                    rate_5m,
                    rate_15m,

                    min_ms,
                    max_ms,
                    mean_ms,
                    median_ms,

                    p75_ms,
                    p95_ms,
                    p99_ms,
                    p999_ms,

                    client_errors,
                    server_errors,
                    errors,
                    timeouts
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                """,
                (
                    replica_id,
                    metric[
                        "category"
                    ],
                    metric[
                        "handler"
                    ],
                    metric[
                        "request_count"
                    ],

                    metric[
                        "mean_rate"
                    ],
                    metric[
                        "rate_1m"
                    ],
                    metric[
                        "rate_5m"
                    ],
                    metric[
                        "rate_15m"
                    ],

                    metric[
                        "min_ms"
                    ],
                    metric[
                        "max_ms"
                    ],
                    metric[
                        "mean_ms"
                    ],
                    metric[
                        "median_ms"
                    ],

                    metric[
                        "p75_ms"
                    ],
                    metric[
                        "p95_ms"
                    ],
                    metric[
                        "p99_ms"
                    ],
                    metric[
                        "p999_ms"
                    ],

                    metric[
                        "client_errors"
                    ],
                    metric[
                        "server_errors"
                    ],
                    metric[
                        "errors"
                    ],
                    metric[
                        "timeouts"
                    ]
                )
            )

        conn.commit()


def collect_request_metrics(
    cluster,
    nodes
):
    cluster_id = (
        cluster["id"]
    )

    try:
        credentials = (
            get_credentials(
                cluster_id
            )
        )

        username = (
            credentials[
                "username"
            ]
        )

        password = (
            credentials[
                "password"
            ]
        )

    except Exception as exc:

        log(
            f"Request metrics credentials "
            f"unavailable for cluster "
            f"{cluster_id} | {exc}"
        )

        return

    replicas = get_cluster_replicas(
        cluster_id
    )

    scheme = (
        cluster.get(
            "solr_scheme"
        )
        or "http"
    )

    total_handlers = 0

    for replica in replicas:

        target, port = (
            get_node_address(
                cluster_id,
                replica[
                    "hostname"
                ],
                nodes
            )
        )

        if not target:

            log(
                f"Request metrics | "
                f"{replica['core_name']} | "
                f"node address unavailable"
            )

            continue

        try:
            metrics = (
                collect_core_request_metrics(
                    target,
                    port,
                    replica[
                        "core_name"
                    ],
                    username,
                    password,
                    scheme
                )
            )

            for metric in metrics:

                save_request_metric(
                    replica[
                        "replica_id"
                    ],
                    metric
                )

                total_handlers += 1

                log(
                    f"Request "
                    f"{replica['core_name']} | "
                    f"{metric['category']}"
                    f"{metric['handler']} | "
                    f"Requests="
                    f"{metric['request_count']} | "
                    f"Rate1m="
                    f"{format_number(metric['rate_1m'], 4)} | "
                    f"Mean="
                    f"{format_number(metric['mean_ms'], 3)}ms | "
                    f"P95="
                    f"{format_number(metric['p95_ms'], 3)}ms | "
                    f"P99="
                    f"{format_number(metric['p99_ms'], 3)}ms | "
                    f"Errors="
                    f"{metric['errors']} | "
                    f"ServerErrors="
                    f"{metric['server_errors']} | "
                    f"Timeouts="
                    f"{metric['timeouts']} | "
                    f"DB=stored"
                )

        except Exception as exc:

            log(
                f"Request metrics error | "
                f"{replica['core_name']} | "
                f"{exc}"
            )

    log(
        f"Request metrics cluster "
        f"{cluster_id} | "
        f"ActiveHandlers="
        f"{total_handlers} | "
        f"DB=synced"
    )

# ============================================================
# Main
# ============================================================

def main():

    log(
        "MonKeeper Collector starting"
    )

    last_discovery_runs = {}
    last_metrics_runs = {}
    last_topology_runs = {}
    last_replica_metrics_runs = {}
    last_request_metrics_runs = {}
	
    while True:

        try:
            clusters = get_clusters()

            now = time.time()

            for cluster in clusters:

                if not cluster.get(
                    "enabled"
                ):
                    continue

                cluster_id = cluster[
                    "id"
                ]

                # ----------------------------------------
                # Discovery
                # ----------------------------------------

                discovery_interval = (
                    cluster.get(
                        "discovery_interval"
                    )
                    or 60
                )

                last_discovery = (
                    last_discovery_runs.get(
                        cluster_id,
                        0
                    )
                )

                if (
                    now - last_discovery
                    >= discovery_interval
                ):

                    try:
                        result = run_discovery(
                            cluster_id
                        )

                        log(
                            f"Discovery cluster "
                            f"{cluster_id} | "
                            f"Solr="
                            f"{result.get('solr_node_count', 0)} | "
                            f"ZooKeeper="
                            f"{result.get('zookeeper_node_count', 0)}"
                        )

                    except Exception as exc:

                        log(
                            f"Discovery error "
                            f"cluster "
                            f"{cluster_id} | "
                            f"{exc}"
                        )

                    last_discovery_runs[
                        cluster_id
                    ] = time.time()

                # ----------------------------------------
                # Refresh nodes
                # ----------------------------------------

                try:
                    nodes = get_nodes()

                except Exception as exc:

                    log(
                        f"Unable to get nodes | "
                        f"{exc}"
                    )

                    continue

                # ----------------------------------------
                # JVM
                # ----------------------------------------

                last_metrics = (
                    last_metrics_runs.get(
                        cluster_id,
                        0
                    )
                )

                if (
                    now - last_metrics
                    >= METRICS_INTERVAL
                ):

                    collect_cluster_metrics(
                        cluster,
                        nodes
                    )

                    last_metrics_runs[
                        cluster_id
                    ] = time.time()

                # ----------------------------------------
                # Topology
                # ----------------------------------------

                last_topology = (
                    last_topology_runs.get(
                        cluster_id,
                        0
                    )
                )

                if (
                    now - last_topology
                    >= TOPOLOGY_INTERVAL
                ):

                    collect_cluster_topology(
                        cluster,
                        nodes
                    )

                    last_topology_runs[
                        cluster_id
                    ] = time.time()

                # ----------------------------------------
                # Replica Document Count
                # ----------------------------------------

                last_replica = (
                    last_replica_metrics_runs.get(
                        cluster_id,
                        0
                    )
                )

                if (
                    now - last_replica
                    >= REPLICA_METRICS_INTERVAL
                ):

                    collect_replica_metrics(
                        cluster,
                        nodes
                    )

                    last_replica_metrics_runs[
                        cluster_id
                    ] = time.time()

                # ----------------------------------------
                # Request / Error / Latency Metrics
                # ----------------------------------------

                last_request = (
                    last_request_metrics_runs.get(
                        cluster_id,
                        0
                    )
                )

                if (
                    now - last_request
                    >= REQUEST_METRICS_INTERVAL
                ):

                    collect_request_metrics(
                        cluster,
                        nodes
                    )

                    last_request_metrics_runs[
                        cluster_id
                    ] = time.time()
        except Exception as exc:

            log(
                f"Collector main loop "
                f"error | "
                f"{exc}"
            )

        time.sleep(
            POLL_INTERVAL
        )


if __name__ == "__main__":
    main()
