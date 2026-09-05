import os
import socket
import re

import psycopg
import requests

from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException
from kazoo.client import KazooClient
from pydantic import BaseModel
from typing import Optional


app = FastAPI(
    title="MonKeeper API",
    version="0.7.0"
)


DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("MONKEEPER_SECRET_KEY")


if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")

if not SECRET_KEY:
    raise RuntimeError("MONKEEPER_SECRET_KEY is not configured")


fernet = Fernet(SECRET_KEY.encode())


# ============================================================
# Models
# ============================================================

class ClusterCreate(BaseModel):
    name: str
    environment: str = "lab"

    zk_connection_string: str
    zk_chroot: str = "/solr"

    solr_scheme: str = "http"
    solr_port: int = 8983

    solr_username: Optional[str] = None

    discovery_interval: int = 60


class NodeAddressUpdate(BaseModel):
    ip_address: str


class SolrCredentialsUpdate(BaseModel):
    username: str
    password: str


# ============================================================
# Helpers
# ============================================================

def resolve_ip(hostname: str):
    try:
        return socket.gethostbyname(hostname)
    except Exception:
        return None


def check_zookeeper_node(
    host: str,
    port: int,
    timeout: float = 3.0
):
    result = {
        "status": "DOWN",
        "role": "unknown",
        "raw": None
    }

    try:
        with socket.create_connection(
            (host, port),
            timeout=timeout
        ) as sock:

            sock.sendall(b"stat\n")
            sock.shutdown(socket.SHUT_WR)

            chunks = []

            while True:
                data = sock.recv(4096)

                if not data:
                    break

                chunks.append(data)

            response = b"".join(chunks).decode(
                "utf-8",
                errors="ignore"
            )

        result["raw"] = response
        result["status"] = "UP"

        match = re.search(
            r"Mode:\s*(\w+)",
            response,
            re.IGNORECASE
        )

        if match:
            result["role"] = match.group(1).lower()

    except Exception as exc:
        result["raw"] = str(exc)

    return result


def encrypt_secret(value: str):
    return fernet.encrypt(
        value.encode()
    ).decode()


def decrypt_secret(value: str):
    return fernet.decrypt(
        value.encode()
    ).decode()


# ============================================================
# Root / Health
# ============================================================

@app.get("/")
def root():
    return {
        "service": "MonKeeper API",
        "version": "0.7.0",
        "status": "running"
    }


@app.get("/health")
def health():
    db_status = "down"

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

        db_status = "up"

    except Exception as exc:
        return {
            "status": "degraded",
            "database": db_status,
            "error": str(exc)
        }

    return {
        "status": "healthy",
        "database": db_status,
        "service": "MonKeeper API"
    }


# ============================================================
# Cluster APIs
# ============================================================

@app.post("/clusters")
def create_cluster(cluster: ClusterCreate):

    if not cluster.name.strip():
        raise HTTPException(
            status_code=400,
            detail="Cluster name is required"
        )

    if not cluster.zk_connection_string.strip():
        raise HTTPException(
            status_code=400,
            detail="ZooKeeper connection string is required"
        )

    if cluster.solr_port < 1 or cluster.solr_port > 65535:
        raise HTTPException(
            status_code=400,
            detail="Invalid Solr port"
        )

    if cluster.discovery_interval < 5:
        raise HTTPException(
            status_code=400,
            detail="Discovery interval must be at least 5 seconds"
        )

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO clusters (
                        name,
                        environment,
                        zk_connection_string,
                        zk_chroot,
                        solr_scheme,
                        solr_port,
                        solr_username,
                        discovery_interval,
                        enabled
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        true
                    )
                    RETURNING id
                    """,
                    (
                        cluster.name.strip(),
                        cluster.environment.strip(),
                        cluster.zk_connection_string.strip(),
                        cluster.zk_chroot.strip(),
                        cluster.solr_scheme.strip(),
                        cluster.solr_port,
                        cluster.solr_username,
                        cluster.discovery_interval
                    )
                )

                cluster_id = cur.fetchone()[0]

            conn.commit()

        return {
            "status": "success",
            "message": "Cluster created",
            "cluster_id": cluster_id,
            "name": cluster.name.strip()
        }

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="A cluster with this name already exists"
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


@app.get("/clusters")
def list_clusters():
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        name,
                        environment,
                        zk_connection_string,
                        zk_chroot,
                        solr_scheme,
                        solr_port,
                        solr_username,
                        discovery_interval,
                        enabled,
                        last_discovery,
                        created_at,
                        updated_at,
(
    SELECT MAX(sm.collected_at)
    FROM solr_metrics sm
    WHERE sm.cluster_id = clusters.id
) AS last_metric_at,
                        CASE
                            WHEN solr_password_encrypted IS NOT NULL
                            THEN true
                            ELSE false
                        END AS credentials_configured
                    FROM clusters
                    ORDER BY id
                    """
                )

                rows = cur.fetchall()

        clusters = []

        for row in rows:
            clusters.append(
                {
                    "id": row[0],
                    "name": row[1],
                    "environment": row[2],
                    "zk_connection_string": row[3],
                    "zk_chroot": row[4],
                    "solr_scheme": row[5],
                    "solr_port": row[6],
                    "solr_username": row[7],
                    "discovery_interval": row[8],
                    "enabled": row[9],
                    "last_discovery": row[10],
                    "created_at": row[11],
                    "updated_at": row[12],
                    "last_metric_at": row[13],
                    "credentials_configured": row[14]
                }
            )

        return {
            "status": "success",
            "count": len(clusters),
            "clusters": clusters
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc)
        }


# ============================================================
# Solr Credentials
# ============================================================

@app.put("/clusters/{cluster_id}/credentials")
def update_solr_credentials(
    cluster_id: int,
    payload: SolrCredentialsUpdate
):
    username = payload.username.strip()
    password = payload.password

    if not username:
        raise HTTPException(
            status_code=400,
            detail="Solr username is required"
        )

    if not password:
        raise HTTPException(
            status_code=400,
            detail="Solr password is required"
        )

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        solr_scheme,
                        solr_port
                    FROM clusters
                    WHERE id = %s
                      AND enabled = true
                    """,
                    (cluster_id,)
                )

                cluster = cur.fetchone()

                if not cluster:
                    raise HTTPException(
                        status_code=404,
                        detail="Cluster not found"
                    )

                cur.execute(
                    """
                    SELECT
                        hostname,
                        ip_address,
                        port
                    FROM nodes
                    WHERE cluster_id = %s
                      AND node_type = 'solr'
                      AND status = 'UP'
                    ORDER BY id
                    LIMIT 1
                    """,
                    (cluster_id,)
                )

                node = cur.fetchone()

        if not node:
            raise HTTPException(
                status_code=400,
                detail="No live Solr node found. Run discovery first."
            )

        scheme = cluster[0] or "http"
        default_port = cluster[1] or 8983

        hostname = node[0]
        ip_address = str(node[1]) if node[1] else None
        port = node[2] or default_port

        target = ip_address or hostname

        url = (
            f"{scheme}://{target}:{port}"
            "/solr/admin/info/system?wt=json"
        )

        try:
            response = requests.get(
                url,
                auth=(username, password),
                timeout=10
            )

        except requests.RequestException as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Unable to reach Solr: {exc}"
            )

        if response.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail="Invalid Solr username or password"
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Solr authentication test failed "
                    f"with HTTP {response.status_code}"
                )
            )

        encrypted_password = encrypt_secret(
            password
        )

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE clusters
                    SET
                        solr_username = %s,
                        solr_password_encrypted = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        username,
                        encrypted_password,
                        cluster_id
                    )
                )

            conn.commit()

        return {
            "status": "success",
            "message": (
                "Solr credentials verified "
                "and stored securely"
            ),
            "cluster_id": cluster_id,
            "username": username,
            "tested_node": {
                "hostname": hostname,
                "ip_address": ip_address,
                "port": port
            }
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


@app.get("/clusters/{cluster_id}/credentials/status")
def solr_credentials_status(cluster_id: int):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        solr_username,
                        solr_password_encrypted IS NOT NULL
                    FROM clusters
                    WHERE id = %s
                    """,
                    (cluster_id,)
                )

                row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Cluster not found"
            )

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "username": row[0],
            "credentials_configured": row[1]
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


# ============================================================
# Internal API for Collector
# ============================================================

@app.get("/internal/clusters/{cluster_id}/credentials")
def internal_cluster_credentials(cluster_id: int):
    """
    Internal endpoint used by the collector.

    MVP only:
    returns the decrypted password to the collector
    over the internal Docker network.

    Do NOT expose this endpoint publicly in production.
    """

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        solr_username,
                        solr_password_encrypted
                    FROM clusters
                    WHERE id = %s
                      AND enabled = true
                    """,
                    (cluster_id,)
                )

                row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Cluster not found"
            )

        username = row[0]
        encrypted_password = row[1]

        if not username or not encrypted_password:
            raise HTTPException(
                status_code=400,
                detail="Solr credentials are not configured"
            )

        password = decrypt_secret(
            encrypted_password
        )

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "username": username,
            "password": password
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


# ============================================================
# Node APIs
# ============================================================

@app.get("/nodes")
def list_nodes():
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        cluster_id,
                        hostname,
                        ip_address,
                        node_type,
                        port,
                        role,
                        discovery_type,
                        status,
                        last_seen,
                        created_at,
                        address_source
                    FROM nodes
                    ORDER BY
                        cluster_id,
                        node_type,
                        hostname
                    """
                )

                rows = cur.fetchall()

        nodes = []

        for row in rows:
            nodes.append(
                {
                    "id": row[0],
                    "cluster_id": row[1],
                    "hostname": row[2],
                    "ip_address": (
                        str(row[3])
                        if row[3]
                        else None
                    ),
                    "node_type": row[4],
                    "port": row[5],
                    "role": row[6],
                    "discovery_type": row[7],
                    "status": row[8],
                    "last_seen": row[9],
                    "created_at": row[10],
                    "address_source": row[11]
                }
            )

        return {
            "status": "success",
            "count": len(nodes),
            "nodes": nodes
        }

    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc)
        }


@app.put("/nodes/{node_id}/address")
def update_node_address(
    node_id: int,
    payload: NodeAddressUpdate
):
    ip_value = payload.ip_address.strip()

    if not ip_value:
        raise HTTPException(
            status_code=400,
            detail="IP address is required"
        )

    try:
        socket.inet_aton(ip_value)

    except OSError:
        raise HTTPException(
            status_code=400,
            detail="Invalid IPv4 address"
        )

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE nodes
                    SET
                        ip_address = %s,
                        address_source = 'wizard'
                    WHERE id = %s
                    RETURNING
                        id,
                        cluster_id,
                        hostname,
                        ip_address,
                        node_type,
                        port,
                        role,
                        status,
                        discovery_type,
                        address_source,
                        last_seen
                    """,
                    (
                        ip_value,
                        node_id
                    )
                )

                row = cur.fetchone()

            conn.commit()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Node not found"
            )

        return {
            "status": "success",
            "message": "Node address updated",
            "node": {
                "id": row[0],
                "cluster_id": row[1],
                "hostname": row[2],
                "ip_address": str(row[3]),
                "node_type": row[4],
                "port": row[5],
                "role": row[6],
                "status": row[7],
                "discovery_type": row[8],
                "address_source": row[9],
                "last_seen": row[10]
            }
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


# ============================================================
# Discovery
# ============================================================

@app.get("/discovery/test/{cluster_id}")
def discovery_test(cluster_id: int):
    try:
        # ----------------------------------------------------
        # Read cluster configuration
        # ----------------------------------------------------

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        name,
                        zk_connection_string,
                        zk_chroot,
                        solr_scheme,
                        solr_port
                    FROM clusters
                    WHERE id = %s
                      AND enabled = true
                    """,
                    (cluster_id,)
                )

                row = cur.fetchone()

        if not row:
            return {
                "status": "error",
                "cluster_id": cluster_id,
                "error": "Cluster not found or disabled"
            }

        cluster_name = row[0]
        zk_hosts = row[1]
        zk_chroot = row[2] or "/solr"
        solr_scheme = row[3] or "http"
        solr_port = row[4] or 8983

        if not zk_hosts:
            return {
                "status": "error",
                "cluster_id": cluster_id,
                "error": "ZooKeeper connection string is empty"
            }

        # ----------------------------------------------------
        # Discover Solr live nodes
        # ----------------------------------------------------

        live_nodes_path = (
            f"{zk_chroot.rstrip('/')}/live_nodes"
        )

        zk = KazooClient(
            hosts=zk_hosts,
            timeout=5.0
        )

        try:
            zk.start(timeout=10)

            if not zk.exists(live_nodes_path):
                return {
                    "status": "error",
                    "cluster_id": cluster_id,
                    "cluster_name": cluster_name,
                    "zookeeper": "connected",
                    "error": (
                        f"Path {live_nodes_path} "
                        "does not exist"
                    )
                }

            live_nodes = zk.get_children(
                live_nodes_path
            )

        finally:
            zk.stop()
            zk.close()

        discovered_solr_nodes = []

        for live_node in live_nodes:

            node_value = live_node

            if node_value.endswith("_solr"):
                node_value = node_value[:-5]

            hostname = node_value
            port = solr_port

            if ":" in node_value:
                hostname, port_value = (
                    node_value.rsplit(":", 1)
                )

                try:
                    port = int(port_value)

                except ValueError:
                    port = solr_port

            ip_address = resolve_ip(hostname)

            address_source = (
                "dns"
                if ip_address
                else "discovered"
            )

            discovered_solr_nodes.append(
                {
                    "raw": live_node,
                    "hostname": hostname,
                    "ip_address": ip_address,
                    "port": port,
                    "role": None,
                    "status": "UP",
                    "address_source": address_source,
                    "url": (
                        f"{solr_scheme}://"
                        f"{hostname}:{port}/solr"
                    )
                }
            )

        # ----------------------------------------------------
        # Discover ZooKeeper nodes
        # ----------------------------------------------------

        discovered_zk_nodes = []

        zk_entries = [
            entry.strip()
            for entry in zk_hosts.split(",")
            if entry.strip()
        ]

        for entry in zk_entries:

            host = entry
            port = 2181

            if ":" in entry:

                host_part, port_part = (
                    entry.rsplit(":", 1)
                )

                host = host_part

                try:
                    port = int(port_part)

                except ValueError:
                    port = 2181

            ip_address = resolve_ip(host)

            if not ip_address:
                ip_address = host

            zk_health = check_zookeeper_node(
                host,
                port
            )

            discovered_zk_nodes.append(
                {
                    "hostname": host,
                    "ip_address": ip_address,
                    "port": port,
                    "role": zk_health["role"],
                    "status": zk_health["status"],
                    "address_source": "configured"
                }
            )

        # ----------------------------------------------------
        # Save inventory
        # ----------------------------------------------------

        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                for node in discovered_solr_nodes:

                    cur.execute(
                        """
                        INSERT INTO nodes (
                            cluster_id,
                            hostname,
                            ip_address,
                            node_type,
                            port,
                            role,
                            discovery_type,
                            status,
                            last_seen,
                            address_source
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            'solr',
                            %s,
                            %s,
                            'auto',
                            %s,
                            NOW(),
                            %s
                        )
                        ON CONFLICT (
                            cluster_id,
                            hostname,
                            node_type
                        )
                        DO UPDATE SET
                            ip_address =
                                CASE
                                    WHEN nodes.address_source
                                         IN ('wizard', 'manual')
                                    THEN nodes.ip_address
                                    ELSE COALESCE(
                                        EXCLUDED.ip_address,
                                        nodes.ip_address
                                    )
                                END,
                            port = EXCLUDED.port,
                            role = EXCLUDED.role,
                            status = EXCLUDED.status,
                            discovery_type = 'auto',
                            last_seen = NOW(),
                            address_source =
                                CASE
                                    WHEN nodes.address_source
                                         IN ('wizard', 'manual')
                                    THEN nodes.address_source
                                    ELSE EXCLUDED.address_source
                                END
                        """,
                        (
                            cluster_id,
                            node["hostname"],
                            node["ip_address"],
                            node["port"],
                            node["role"],
                            node["status"],
                            node["address_source"]
                        )
                    )

                for node in discovered_zk_nodes:

                    cur.execute(
                        """
                        INSERT INTO nodes (
                            cluster_id,
                            hostname,
                            ip_address,
                            node_type,
                            port,
                            role,
                            discovery_type,
                            status,
                            last_seen,
                            address_source
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            'zookeeper',
                            %s,
                            %s,
                            'configured',
                            %s,
                            NOW(),
                            %s
                        )
                        ON CONFLICT (
                            cluster_id,
                            hostname,
                            node_type
                        )
                        DO UPDATE SET
                            ip_address = EXCLUDED.ip_address,
                            port = EXCLUDED.port,
                            role = EXCLUDED.role,
                            status = EXCLUDED.status,
                            last_seen = NOW(),
                            address_source = EXCLUDED.address_source
                        """,
                        (
                            cluster_id,
                            node["hostname"],
                            node["ip_address"],
                            node["port"],
                            node["role"],
                            node["status"],
                            node["address_source"]
                        )
                    )

                cur.execute(
                    """
                    UPDATE clusters
                    SET
                        last_discovery = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (cluster_id,)
                )

            conn.commit()

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
            "zookeeper": "connected",
            "zk_hosts": zk_hosts,
            "zk_chroot": zk_chroot,
            "live_nodes_path": live_nodes_path,
            "solr_nodes": discovered_solr_nodes,
            "solr_node_count": len(
                discovered_solr_nodes
            ),
            "zookeeper_nodes": discovered_zk_nodes,
            "zookeeper_node_count": len(
                discovered_zk_nodes
            ),
            "database_sync": "completed"
        }

    except Exception as exc:
        return {
            "status": "error",
            "cluster_id": cluster_id,
            "error": str(exc)
        }
# ============================================================
# Solr Metrics APIs
# ============================================================

@app.get("/metrics/solr/current")
def solr_metrics_current():
    """
    Return the latest stored metric for each Solr node.
    """

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT DISTINCT ON (m.node_id)
                        m.node_id,
                        n.cluster_id,
                        n.hostname,
                        n.ip_address,
                        m.collected_at,
                        m.heap_used_mb,
                        m.heap_max_mb,
                        m.heap_usage_percent,
                        m.young_gc_count,
                        m.young_gc_time_ms,
                        m.old_gc_count,
                        m.old_gc_time_ms,
                        m.process_cpu_percent,
                        m.system_cpu_percent,
                        m.thread_count,
                        m.deadlock_count,
                        m.ram_total_mb,
                        m.ram_free_mb,
                        m.open_file_descriptors
                    FROM solr_metrics m
                    JOIN nodes n
                      ON n.id = m.node_id
                    WHERE n.node_type = 'solr'
                    ORDER BY
                        m.node_id,
                        m.collected_at DESC
                    """
                )

                rows = cur.fetchall()

        metrics = []

        for row in rows:
            metrics.append(
                {
                    "node_id": row[0],
                    "cluster_id": row[1],
                    "hostname": row[2],
                    "ip_address": (
                        str(row[3])
                        if row[3]
                        else None
                    ),
                    "collected_at": row[4],

                    "heap_used_mb": row[5],
                    "heap_max_mb": row[6],
                    "heap_usage_percent": row[7],

                    "young_gc_count": row[8],
                    "young_gc_time_ms": row[9],

                    "old_gc_count": row[10],
                    "old_gc_time_ms": row[11],

                    "process_cpu_percent": row[12],
                    "system_cpu_percent": row[13],

                    "thread_count": row[14],
                    "deadlock_count": row[15],

                    "ram_total_mb": row[16],
                    "ram_free_mb": row[17],

                    "open_file_descriptors": row[18]
                }
            )

        return {
            "status": "success",
            "count": len(metrics),
            "metrics": metrics
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


@app.get("/metrics/solr/history")
def solr_metrics_history(
    node_id: int,
    minutes: int = 60
):
    """
    Return historical metrics for one Solr node.

    Example:
    /metrics/solr/history?node_id=1&minutes=60
    """

    if minutes < 1:
        raise HTTPException(
            status_code=400,
            detail="minutes must be greater than 0"
        )

    if minutes > 10080:
        raise HTTPException(
            status_code=400,
            detail="Maximum history range is 10080 minutes"
        )

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        hostname,
                        ip_address,
                        cluster_id
                    FROM nodes
                    WHERE id = %s
                      AND node_type = 'solr'
                    """,
                    (node_id,)
                )

                node = cur.fetchone()

                if not node:
                    raise HTTPException(
                        status_code=404,
                        detail="Solr node not found"
                    )

                cur.execute(
                    """
                    SELECT
                        collected_at,
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
                    FROM solr_metrics
                    WHERE node_id = %s
                      AND collected_at >=
                          NOW() - (%s * INTERVAL '1 minute')
                    ORDER BY collected_at ASC
                    """,
                    (
                        node_id,
                        minutes
                    )
                )

                rows = cur.fetchall()

        history = []

        for row in rows:
            history.append(
                {
                    "collected_at": row[0],

                    "heap_used_mb": row[1],
                    "heap_max_mb": row[2],
                    "heap_usage_percent": row[3],

                    "young_gc_count": row[4],
                    "young_gc_time_ms": row[5],

                    "old_gc_count": row[6],
                    "old_gc_time_ms": row[7],

                    "process_cpu_percent": row[8],
                    "system_cpu_percent": row[9],

                    "thread_count": row[10],
                    "deadlock_count": row[11],

                    "ram_total_mb": row[12],
                    "ram_free_mb": row[13],

                    "open_file_descriptors": row[14]
                }
            )

        return {
            "status": "success",

            "node": {
                "id": node[0],
                "hostname": node[1],
                "ip_address": (
                    str(node[2])
                    if node[2]
                    else None
                ),
                "cluster_id": node[3]
            },

            "range_minutes": minutes,
            "count": len(history),
            "history": history
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )

# ============================================================
# Solr Topology / Consistency APIs
# ============================================================

@app.get("/solr/topology")
def solr_topology(cluster_id: int = 1):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        c.id,
                        c.name,
                        c.health,
                        c.replication_factor,
                        s.id,
                        s.name,
                        s.state,
                        s.health,
                        r.id,
                        r.replica_name,
                        r.core_name,
                        r.hostname,
                        r.replica_type,
                        r.state,
                        r.is_leader
                    FROM solr_collections c
                    JOIN solr_shards s
                      ON s.collection_id = c.id
                    JOIN solr_replicas r
                      ON r.shard_id = s.id
                    WHERE c.cluster_id = %s
                    ORDER BY
                        c.name,
                        s.name,
                        r.hostname
                    """,
                    (cluster_id,)
                )

                rows = cur.fetchall()

        collections = {}

        for row in rows:
            (
                collection_id,
                collection_name,
                collection_health,
                replication_factor,
                shard_id,
                shard_name,
                shard_state,
                shard_health,
                replica_id,
                replica_name,
                core_name,
                hostname,
                replica_type,
                replica_state,
                is_leader
            ) = row

            if collection_id not in collections:
                collections[collection_id] = {
                    "id": collection_id,
                    "name": collection_name,
                    "health": collection_health,
                    "replication_factor": replication_factor,
                    "shards": {}
                }

            if shard_id not in collections[collection_id]["shards"]:
                collections[collection_id]["shards"][shard_id] = {
                    "id": shard_id,
                    "name": shard_name,
                    "state": shard_state,
                    "health": shard_health,
                    "replicas": []
                }

            collections[collection_id]["shards"][shard_id]["replicas"].append(
                {
                    "id": replica_id,
                    "replica_name": replica_name,
                    "core_name": core_name,
                    "hostname": hostname,
                    "replica_type": replica_type,
                    "state": replica_state,
                    "is_leader": is_leader
                }
            )

        output = []

        for collection in collections.values():
            collection["shards"] = list(
                collection["shards"].values()
            )
            output.append(collection)

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "collections": output
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


@app.get("/solr/consistency")
def solr_consistency(cluster_id: int = 1):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH latest_replica_metrics AS (
                        SELECT DISTINCT ON (rm.replica_id)
                            rm.replica_id,
                            rm.doc_count,
                            rm.query_time_ms,
                            rm.collection_status,
                            rm.collected_at
                        FROM solr_replica_metrics rm
                        ORDER BY
                            rm.replica_id,
                            rm.collected_at DESC
                    )
                    SELECT
                        c.name,
                        s.id,
                        s.name,
                        s.state,
                        s.health,
                        r.id,
                        r.core_name,
                        r.hostname,
                        r.is_leader,
                        r.state,
                        lrm.doc_count,
                        lrm.query_time_ms,
                        lrm.collection_status,
                        lrm.collected_at
                    FROM solr_collections c
                    JOIN solr_shards s
                      ON s.collection_id = c.id
                    JOIN solr_replicas r
                      ON r.shard_id = s.id
                    LEFT JOIN latest_replica_metrics lrm
                      ON lrm.replica_id = r.id
                    WHERE c.cluster_id = %s
                    ORDER BY
                        c.name,
                        s.name,
                        r.hostname
                    """,
                    (cluster_id,)
                )

                rows = cur.fetchall()

        shards = {}

        for row in rows:
            (
                collection_name,
                shard_id,
                shard_name,
                shard_state,
                shard_health,
                replica_id,
                core_name,
                hostname,
                is_leader,
                replica_state,
                doc_count,
                query_time_ms,
                collection_status,
                collected_at
            ) = row

            if shard_id not in shards:
                shards[shard_id] = {
                    "collection": collection_name,
                    "shard": shard_name,
                    "shard_state": shard_state,
                    "shard_health": shard_health,
                    "replicas": []
                }

            shards[shard_id]["replicas"].append(
                {
                    "replica_id": replica_id,
                    "core_name": core_name,
                    "hostname": hostname,
                    "is_leader": is_leader,
                    "state": replica_state,
                    "doc_count": doc_count,
                    "query_time_ms": query_time_ms,
                    "collection_status": collection_status,
                    "collected_at": collected_at
                }
            )

        result = []

        for shard in shards.values():
            valid_counts = [
                r["doc_count"]
                for r in shard["replicas"]
                if r["doc_count"] is not None
            ]

            if valid_counts:
                min_docs = min(valid_counts)
                max_docs = max(valid_counts)
                doc_diff = max_docs - min_docs
            else:
                min_docs = None
                max_docs = None
                doc_diff = None

            all_replicas_have_data = (
                len(valid_counts)
                == len(shard["replicas"])
            )

            all_replicas_active = all(
                r["state"] == "active"
                for r in shard["replicas"]
            )

            if (
                doc_diff == 0
                and all_replicas_have_data
                and all_replicas_active
            ):
                consistency_status = "CONSISTENT"

            elif (
                doc_diff is not None
                and doc_diff > 0
            ):
                consistency_status = "MISMATCH"

            else:
                consistency_status = "UNKNOWN"

            shard["min_docs"] = min_docs
            shard["max_docs"] = max_docs
            shard["doc_diff"] = doc_diff
            shard["consistency_status"] = consistency_status

            result.append(shard)

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "count": len(result),
            "shards": result
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


@app.get("/solr/summary")
def solr_summary(cluster_id: int = 1):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM solr_collections
                    WHERE cluster_id = %s
                    """,
                    (cluster_id,)
                )
                collections_count = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM solr_shards s
                    JOIN solr_collections c
                      ON c.id = s.collection_id
                    WHERE c.cluster_id = %s
                    """,
                    (cluster_id,)
                )
                shards_count = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM solr_replicas r
                    JOIN solr_shards s
                      ON s.id = r.shard_id
                    JOIN solr_collections c
                      ON c.id = s.collection_id
                    WHERE c.cluster_id = %s
                    """,
                    (cluster_id,)
                )
                replicas_count = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM solr_replicas r
                    JOIN solr_shards s
                      ON s.id = r.shard_id
                    JOIN solr_collections c
                      ON c.id = s.collection_id
                    WHERE c.cluster_id = %s
                      AND r.state = 'active'
                    """,
                    (cluster_id,)
                )
                active_replicas = cur.fetchone()[0]

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM solr_replicas r
                    JOIN solr_shards s
                      ON s.id = r.shard_id
                    JOIN solr_collections c
                      ON c.id = s.collection_id
                    WHERE c.cluster_id = %s
                      AND r.is_leader = true
                    """,
                    (cluster_id,)
                )
                leader_count = cur.fetchone()[0]

        consistency = solr_consistency(
            cluster_id
        )

        consistent_shards = sum(
            1
            for shard in consistency["shards"]
            if shard["consistency_status"] == "CONSISTENT"
        )

        mismatch_shards = sum(
            1
            for shard in consistency["shards"]
            if shard["consistency_status"] == "MISMATCH"
        )

        unknown_shards = sum(
            1
            for shard in consistency["shards"]
            if shard["consistency_status"] == "UNKNOWN"
        )

        if (
            mismatch_shards == 0
            and unknown_shards == 0
            and active_replicas == replicas_count
        ):
            overall_status = "HEALTHY"
        elif mismatch_shards > 0:
            overall_status = "WARNING"
        else:
            overall_status = "DEGRADED"

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "overall_status": overall_status,
            "collections": collections_count,
            "shards": shards_count,
            "replicas": replicas_count,
            "active_replicas": active_replicas,
            "leaders": leader_count,
            "consistent_shards": consistent_shards,
            "mismatch_shards": mismatch_shards,
            "unknown_shards": unknown_shards
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )

# ============================================================
# Solr Request Metrics - Current
# ============================================================

@app.get("/metrics/requests/current")
def solr_request_metrics_current(
    cluster_id: int = 1
):
    """
    Return the latest request metrics for every active
    Solr request handler / replica in the cluster.
    """

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT DISTINCT ON (
                        rm.replica_id,
                        rm.category,
                        rm.handler
                    )
                        rm.replica_id,
                        c.id AS collection_id,
                        c.name AS collection_name,
                        s.id AS shard_id,
                        s.name AS shard_name,
                        r.core_name,
                        r.hostname,
                        r.is_leader,
                        rm.collected_at,
                        rm.category,
                        rm.handler,
                        rm.request_count,
                        rm.mean_rate,
                        rm.rate_1m,
                        rm.rate_5m,
                        rm.rate_15m,
                        rm.min_ms,
                        rm.max_ms,
                        rm.mean_ms,
                        rm.median_ms,
                        rm.p75_ms,
                        rm.p95_ms,
                        rm.p99_ms,
                        rm.p999_ms,
                        rm.client_errors,
                        rm.server_errors,
                        rm.errors,
                        rm.timeouts
                    FROM solr_request_metrics rm
                    JOIN solr_replicas r
                      ON r.id = rm.replica_id
                    JOIN solr_shards s
                      ON s.id = r.shard_id
                    JOIN solr_collections c
                      ON c.id = s.collection_id
                    WHERE c.cluster_id = %s
                    ORDER BY
                        rm.replica_id,
                        rm.category,
                        rm.handler,
                        rm.collected_at DESC
                    """,
                    (
                        cluster_id,
                    )
                )

                rows = cur.fetchall()

        metrics = []

        for row in rows:
            metrics.append(
                {
                    "replica_id": row[0],
                    "collection_id": row[1],
                    "collection": row[2],
                    "shard_id": row[3],
                    "shard": row[4],
                    "core_name": row[5],
                    "hostname": row[6],
                    "is_leader": row[7],
                    "collected_at": row[8],
                    "category": row[9],
                    "handler": row[10],
                    "request_count": row[11],
                    "mean_rate": row[12],
                    "rate_1m": row[13],
                    "rate_5m": row[14],
                    "rate_15m": row[15],
                    "min_ms": row[16],
                    "max_ms": row[17],
                    "mean_ms": row[18],
                    "median_ms": row[19],
                    "p75_ms": row[20],
                    "p95_ms": row[21],
                    "p99_ms": row[22],
                    "p999_ms": row[23],
                    "client_errors": row[24],
                    "server_errors": row[25],
                    "errors": row[26],
                    "timeouts": row[27]
                }
            )

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "count": len(metrics),
            "metrics": metrics
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )
# ============================================================
# Solr Request Metrics - Summary
# ============================================================

@app.get("/metrics/requests/summary")
def solr_request_metrics_summary(
    cluster_id: int = 1
):
    """
    Return a dashboard-friendly summary using the latest
    request metric for each replica/category/handler.
    """

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    WITH latest AS (
                        SELECT DISTINCT ON (
                            rm.replica_id,
                            rm.category,
                            rm.handler
                        )
                            rm.replica_id,
                            rm.category,
                            rm.handler,
                            rm.collected_at,
                            rm.request_count,
                            rm.rate_1m,
                            rm.rate_5m,
                            rm.rate_15m,
                            rm.mean_ms,
                            rm.p95_ms,
                            rm.p99_ms,
                            rm.client_errors,
                            rm.server_errors,
                            rm.errors,
                            rm.timeouts,
                            r.core_name,
                            r.hostname,
                            r.is_leader,
                            s.name AS shard_name,
                            c.name AS collection_name
                        FROM solr_request_metrics rm
                        JOIN solr_replicas r
                          ON r.id = rm.replica_id
                        JOIN solr_shards s
                          ON s.id = r.shard_id
                        JOIN solr_collections c
                          ON c.id = s.collection_id
                        WHERE c.cluster_id = %s
                        ORDER BY
                            rm.replica_id,
                            rm.category,
                            rm.handler,
                            rm.collected_at DESC
                    )
                    SELECT
                        COUNT(*) AS active_handlers,

                        COALESCE(
                            SUM(request_count),
                            0
                        ) AS cumulative_requests,

                        COALESCE(
                            SUM(rate_1m),
                            0
                        ) AS rate_1m,

                        COALESCE(
                            SUM(rate_5m),
                            0
                        ) AS rate_5m,

                        COALESCE(
                            SUM(rate_15m),
                            0
                        ) AS rate_15m,

                        MAX(mean_ms) AS max_mean_ms,
                        MAX(p95_ms) AS max_p95_ms,
                        MAX(p99_ms) AS max_p99_ms,

                        COALESCE(
                            SUM(client_errors),
                            0
                        ) AS client_errors,

                        COALESCE(
                            SUM(server_errors),
                            0
                        ) AS server_errors,

                        COALESCE(
                            SUM(errors),
                            0
                        ) AS errors,

                        COALESCE(
                            SUM(timeouts),
                            0
                        ) AS timeouts,

                        MAX(collected_at)
                            AS collected_at

                    FROM latest
                    """,
                    (
                        cluster_id,
                    )
                )

                summary_row = cur.fetchone()

                # ----------------------------------------
                # Slowest handler by P95
                # ----------------------------------------

                cur.execute(
                    """
                    WITH latest AS (
                        SELECT DISTINCT ON (
                            rm.replica_id,
                            rm.category,
                            rm.handler
                        )
                            rm.replica_id,
                            rm.category,
                            rm.handler,
                            rm.collected_at,
                            rm.mean_ms,
                            rm.p95_ms,
                            rm.p99_ms,
                            r.core_name,
                            r.hostname,
                            r.is_leader,
                            s.name AS shard_name,
                            c.name AS collection_name
                        FROM solr_request_metrics rm
                        JOIN solr_replicas r
                          ON r.id = rm.replica_id
                        JOIN solr_shards s
                          ON s.id = r.shard_id
                        JOIN solr_collections c
                          ON c.id = s.collection_id
                        WHERE c.cluster_id = %s
                        ORDER BY
                            rm.replica_id,
                            rm.category,
                            rm.handler,
                            rm.collected_at DESC
                    )
                    SELECT
                        collection_name,
                        shard_name,
                        core_name,
                        hostname,
                        is_leader,
                        category,
                        handler,
                        mean_ms,
                        p95_ms,
                        p99_ms
                    FROM latest
                    WHERE p95_ms IS NOT NULL
                    ORDER BY p95_ms DESC
                    LIMIT 1
                    """,
                    (
                        cluster_id,
                    )
                )

                slowest_row = cur.fetchone()

        slowest_handler = None

        if slowest_row:
            slowest_handler = {
                "collection": slowest_row[0],
                "shard": slowest_row[1],
                "core_name": slowest_row[2],
                "hostname": slowest_row[3],
                "is_leader": slowest_row[4],
                "category": slowest_row[5],
                "handler": slowest_row[6],
                "mean_ms": slowest_row[7],
                "p95_ms": slowest_row[8],
                "p99_ms": slowest_row[9]
            }

        active_handlers = summary_row[0] or 0
        cumulative_requests = summary_row[1] or 0

        rate_1m = float(
            summary_row[2] or 0
        )

        rate_5m = float(
            summary_row[3] or 0
        )

        rate_15m = float(
            summary_row[4] or 0
        )

        client_errors = summary_row[8] or 0
        server_errors = summary_row[9] or 0
        errors = summary_row[10] or 0
        timeouts = summary_row[11] or 0

        total_errors = (
            client_errors
            + server_errors
            + errors
        )

        return {
            "status": "success",
            "cluster_id": cluster_id,

            "active_handlers":
                active_handlers,

            "cumulative_requests":
                cumulative_requests,

            "request_rate": {
                "rate_1m":
                    rate_1m,

                "rate_5m":
                    rate_5m,

                "rate_15m":
                    rate_15m
            },

            "latency": {
                "max_mean_ms":
                    summary_row[5],

                "max_p95_ms":
                    summary_row[6],

                "max_p99_ms":
                    summary_row[7]
            },

            "errors": {
                "client_errors":
                    client_errors,

                "server_errors":
                    server_errors,

                "errors":
                    errors,

                "total_errors":
                    total_errors,

                "timeouts":
                    timeouts
            },

            "slowest_handler":
                slowest_handler,

            "collected_at":
                summary_row[12]
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )
# ============================================================
# Solr Request Metrics - History
# ============================================================

# ============================================================
# Solr Request Metrics - History
# ============================================================

@app.get("/metrics/requests/history")
def solr_request_metrics_history(
    cluster_id: int = 1,
    minutes: int = 60
):
    """
    Return cluster-level request metrics grouped into 1-minute buckets.
    """

    if minutes < 1:
        raise HTTPException(
            status_code=400,
            detail="minutes must be greater than 0"
        )

    if minutes > 10080:
        raise HTTPException(
            status_code=400,
            detail="Maximum history range is 10080 minutes"
        )

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        date_trunc(
                            'minute',
                            rm.collected_at
                        ) AS bucket,

                        COALESCE(
                            SUM(rm.rate_1m),
                            0
                        ) AS rate_1m,

                        COALESCE(
                            SUM(rm.rate_5m),
                            0
                        ) AS rate_5m,

                        COALESCE(
                            SUM(rm.rate_15m),
                            0
                        ) AS rate_15m,

                        MAX(rm.mean_ms)
                            AS max_mean_ms,

                        MAX(rm.p95_ms)
                            AS max_p95_ms,

                        MAX(rm.p99_ms)
                            AS max_p99_ms,

                        COALESCE(
                            SUM(rm.client_errors),
                            0
                        ) AS client_errors,

                        COALESCE(
                            SUM(rm.server_errors),
                            0
                        ) AS server_errors,

                        COALESCE(
                            SUM(rm.errors),
                            0
                        ) AS errors,

                        COALESCE(
                            SUM(rm.timeouts),
                            0
                        ) AS timeouts

                    FROM solr_request_metrics rm

                    JOIN solr_replicas r
                      ON r.id = rm.replica_id

                    JOIN solr_shards s
                      ON s.id = r.shard_id

                    JOIN solr_collections c
                      ON c.id = s.collection_id

                    WHERE
                        c.cluster_id = %s

                        AND rm.collected_at >=
                            NOW()
                            - (%s * INTERVAL '1 minute')

                    GROUP BY
                        date_trunc(
                            'minute',
                            rm.collected_at
                        )

                    ORDER BY
                        bucket ASC
                    """,
                    (
                        cluster_id,
                        minutes
                    )
                )

                rows = cur.fetchall()

        history = []

        for row in rows:
            history.append(
                {
                    "collected_at": row[0],

                    "rate_1m": float(row[1] or 0),
                    "rate_5m": float(row[2] or 0),
                    "rate_15m": float(row[3] or 0),

                    "max_mean_ms": (
                        float(row[4])
                        if row[4] is not None
                        else None
                    ),

                    "max_p95_ms": (
                        float(row[5])
                        if row[5] is not None
                        else None
                    ),

                    "max_p99_ms": (
                        float(row[6])
                        if row[6] is not None
                        else None
                    ),

                    "client_errors": int(row[7] or 0),
                    "server_errors": int(row[8] or 0),
                    "errors": int(row[9] or 0),
                    "timeouts": int(row[10] or 0)
                }
            )

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "range_minutes": minutes,
            "bucket_seconds": 60,
            "count": len(history),
            "history": history
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )
class ClusterCreate(BaseModel):
    name: str
    environment: str = "lab"
    zk_connection_string: Optional[str] = None
    zk_chroot: str = "/solr"
    solr_scheme: str = "http"
    solr_port: int = 8983
    discovery_interval: int = 60
    enabled: bool = True


class ClusterUpdate(BaseModel):
    name: Optional[str] = None
    environment: Optional[str] = None
    zk_connection_string: Optional[str] = None
    zk_chroot: Optional[str] = None
    solr_scheme: Optional[str] = None
    solr_port: Optional[int] = None
    discovery_interval: Optional[int] = None
    enabled: Optional[bool] = None
# ============================================================
# Cluster Management
# ============================================================


@app.put("/clusters/{cluster_id}")
def update_cluster(
    cluster_id: int,
    payload: ClusterUpdate
):
    updates = []
    values = []

    fields = {
        "name": payload.name,
        "environment": payload.environment,
        "zk_connection_string": payload.zk_connection_string,
        "zk_chroot": payload.zk_chroot,
        "solr_scheme": payload.solr_scheme,
        "solr_port": payload.solr_port,
        "discovery_interval": payload.discovery_interval,
        "enabled": payload.enabled
    }

    for column, value in fields.items():
        if value is not None:
            updates.append(
                f"{column} = %s"
            )
            values.append(value)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No fields provided"
        )

    updates.append(
        "updated_at = NOW()"
    )

    values.append(
        cluster_id
    )

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    f"""
                    UPDATE clusters
                    SET {", ".join(updates)}
                    WHERE id = %s
                    RETURNING id
                    """,
                    values
                )

                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Cluster not found"
                    )

            conn.commit()

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "message": "Cluster updated"
        }

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="Cluster name already exists"
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


@app.patch("/clusters/{cluster_id}/enabled")
def set_cluster_enabled(
    cluster_id: int,
    enabled: bool
):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    UPDATE clusters
                    SET
                        enabled = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                    """,
                    (
                        enabled,
                        cluster_id
                    )
                )

                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Cluster not found"
                    )

            conn.commit()

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "enabled": enabled
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


@app.delete("/clusters/{cluster_id}")
def delete_cluster(
    cluster_id: int
):
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    DELETE FROM clusters
                    WHERE id = %s
                    RETURNING name
                    """,
                    (
                        cluster_id,
                    )
                )

                row = cur.fetchone()

                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail="Cluster not found"
                    )

            conn.commit()

        return {
            "status": "success",
            "cluster_id": cluster_id,
            "name": row[0],
            "message": "Cluster deleted"
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )
