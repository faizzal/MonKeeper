--
-- PostgreSQL database dump
--

\restrict IMpgk4uqrUxKNPdRTY2Cag2hi17wuM5OYpDt3f4F1bbPZZGtxRlGGamPnSpWdhx

-- Dumped from database version 17.11 (Debian 17.11-1.pgdg13+2)
-- Dumped by pg_dump version 17.11 (Debian 17.11-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: clusters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clusters (
    id bigint NOT NULL,
    name character varying(150) NOT NULL,
    environment character varying(50) DEFAULT 'lab'::character varying NOT NULL,
    solr_username character varying(150),
    solr_password_encrypted text,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    zk_connection_string text,
    zk_chroot character varying(255) DEFAULT '/solr'::character varying,
    solr_scheme character varying(10) DEFAULT 'http'::character varying,
    solr_port integer DEFAULT 8983,
    discovery_interval integer DEFAULT 60,
    last_discovery timestamp with time zone
);


--
-- Name: clusters_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clusters_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clusters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clusters_id_seq OWNED BY public.clusters.id;


--
-- Name: nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.nodes (
    id bigint NOT NULL,
    cluster_id bigint NOT NULL,
    hostname character varying(255) NOT NULL,
    ip_address inet,
    node_type character varying(50) NOT NULL,
    port integer,
    role character varying(50),
    discovery_type character varying(50) DEFAULT 'auto'::character varying NOT NULL,
    status character varying(30) DEFAULT 'UNKNOWN'::character varying NOT NULL,
    last_seen timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    address_source character varying(30) DEFAULT 'discovered'::character varying
);


--
-- Name: nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.nodes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nodes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.nodes_id_seq OWNED BY public.nodes.id;


--
-- Name: settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.settings (
    id bigint NOT NULL,
    setting_key character varying(150) NOT NULL,
    setting_value text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.settings_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.settings_id_seq OWNED BY public.settings.id;


--
-- Name: solr_collections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solr_collections (
    id bigint NOT NULL,
    cluster_id bigint NOT NULL,
    name character varying(255) NOT NULL,
    config_name character varying(255),
    replication_factor integer,
    nrt_replicas integer,
    tlog_replicas integer,
    pull_replicas integer,
    router_name character varying(100),
    health character varying(30),
    creation_time_ms bigint,
    znode_version integer,
    last_seen timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: solr_collections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solr_collections_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solr_collections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solr_collections_id_seq OWNED BY public.solr_collections.id;


--
-- Name: solr_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solr_metrics (
    id bigint NOT NULL,
    cluster_id bigint NOT NULL,
    node_id bigint NOT NULL,
    collected_at timestamp with time zone DEFAULT now() NOT NULL,
    heap_used_mb double precision,
    heap_max_mb double precision,
    heap_usage_percent double precision,
    young_gc_count bigint,
    young_gc_time_ms bigint,
    old_gc_count bigint,
    old_gc_time_ms bigint,
    process_cpu_percent double precision,
    system_cpu_percent double precision,
    thread_count integer,
    deadlock_count integer,
    ram_total_mb double precision,
    ram_free_mb double precision,
    open_file_descriptors bigint
);


--
-- Name: solr_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solr_metrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solr_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solr_metrics_id_seq OWNED BY public.solr_metrics.id;


--
-- Name: solr_replica_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solr_replica_metrics (
    id bigint NOT NULL,
    replica_id bigint NOT NULL,
    collected_at timestamp with time zone DEFAULT now() NOT NULL,
    doc_count bigint,
    query_time_ms double precision,
    collection_status character varying(30) DEFAULT 'OK'::character varying
);


--
-- Name: solr_replica_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solr_replica_metrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solr_replica_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solr_replica_metrics_id_seq OWNED BY public.solr_replica_metrics.id;


--
-- Name: solr_replicas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solr_replicas (
    id bigint NOT NULL,
    shard_id bigint NOT NULL,
    replica_name character varying(255) NOT NULL,
    core_name character varying(255) NOT NULL,
    node_name character varying(255),
    hostname character varying(255),
    base_url text,
    replica_type character varying(30),
    state character varying(50),
    is_leader boolean DEFAULT false NOT NULL,
    last_seen timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: solr_replicas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solr_replicas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solr_replicas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solr_replicas_id_seq OWNED BY public.solr_replicas.id;


--
-- Name: solr_request_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solr_request_metrics (
    id bigint NOT NULL,
    replica_id bigint NOT NULL,
    collected_at timestamp with time zone DEFAULT now() NOT NULL,
    category character varying(30) NOT NULL,
    handler character varying(255) NOT NULL,
    request_count bigint,
    mean_rate double precision,
    rate_1m double precision,
    rate_5m double precision,
    rate_15m double precision,
    min_ms double precision,
    max_ms double precision,
    mean_ms double precision,
    median_ms double precision,
    p75_ms double precision,
    p95_ms double precision,
    p99_ms double precision,
    p999_ms double precision,
    client_errors bigint,
    server_errors bigint,
    errors bigint,
    timeouts bigint
);


--
-- Name: solr_request_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solr_request_metrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solr_request_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solr_request_metrics_id_seq OWNED BY public.solr_request_metrics.id;


--
-- Name: solr_shards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.solr_shards (
    id bigint NOT NULL,
    collection_id bigint NOT NULL,
    name character varying(255) NOT NULL,
    hash_range character varying(255),
    state character varying(50),
    health character varying(30),
    last_seen timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: solr_shards_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.solr_shards_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: solr_shards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.solr_shards_id_seq OWNED BY public.solr_shards.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    username character varying(100) NOT NULL,
    password_hash text NOT NULL,
    role character varying(50) DEFAULT 'admin'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: clusters id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clusters ALTER COLUMN id SET DEFAULT nextval('public.clusters_id_seq'::regclass);


--
-- Name: nodes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nodes ALTER COLUMN id SET DEFAULT nextval('public.nodes_id_seq'::regclass);


--
-- Name: settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings ALTER COLUMN id SET DEFAULT nextval('public.settings_id_seq'::regclass);


--
-- Name: solr_collections id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_collections ALTER COLUMN id SET DEFAULT nextval('public.solr_collections_id_seq'::regclass);


--
-- Name: solr_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_metrics ALTER COLUMN id SET DEFAULT nextval('public.solr_metrics_id_seq'::regclass);


--
-- Name: solr_replica_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_replica_metrics ALTER COLUMN id SET DEFAULT nextval('public.solr_replica_metrics_id_seq'::regclass);


--
-- Name: solr_replicas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_replicas ALTER COLUMN id SET DEFAULT nextval('public.solr_replicas_id_seq'::regclass);


--
-- Name: solr_request_metrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_request_metrics ALTER COLUMN id SET DEFAULT nextval('public.solr_request_metrics_id_seq'::regclass);


--
-- Name: solr_shards id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_shards ALTER COLUMN id SET DEFAULT nextval('public.solr_shards_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: clusters clusters_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clusters
    ADD CONSTRAINT clusters_name_key UNIQUE (name);


--
-- Name: clusters clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clusters
    ADD CONSTRAINT clusters_pkey PRIMARY KEY (id);


--
-- Name: nodes nodes_cluster_id_hostname_node_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT nodes_cluster_id_hostname_node_type_key UNIQUE (cluster_id, hostname, node_type);


--
-- Name: nodes nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT nodes_pkey PRIMARY KEY (id);


--
-- Name: settings settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_pkey PRIMARY KEY (id);


--
-- Name: settings settings_setting_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.settings
    ADD CONSTRAINT settings_setting_key_key UNIQUE (setting_key);


--
-- Name: solr_collections solr_collections_cluster_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_collections
    ADD CONSTRAINT solr_collections_cluster_id_name_key UNIQUE (cluster_id, name);


--
-- Name: solr_collections solr_collections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_collections
    ADD CONSTRAINT solr_collections_pkey PRIMARY KEY (id);


--
-- Name: solr_metrics solr_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_metrics
    ADD CONSTRAINT solr_metrics_pkey PRIMARY KEY (id);


--
-- Name: solr_replica_metrics solr_replica_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_replica_metrics
    ADD CONSTRAINT solr_replica_metrics_pkey PRIMARY KEY (id);


--
-- Name: solr_replicas solr_replicas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_replicas
    ADD CONSTRAINT solr_replicas_pkey PRIMARY KEY (id);


--
-- Name: solr_replicas solr_replicas_shard_id_replica_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_replicas
    ADD CONSTRAINT solr_replicas_shard_id_replica_name_key UNIQUE (shard_id, replica_name);


--
-- Name: solr_request_metrics solr_request_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_request_metrics
    ADD CONSTRAINT solr_request_metrics_pkey PRIMARY KEY (id);


--
-- Name: solr_shards solr_shards_collection_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_shards
    ADD CONSTRAINT solr_shards_collection_id_name_key UNIQUE (collection_id, name);


--
-- Name: solr_shards solr_shards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_shards
    ADD CONSTRAINT solr_shards_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: idx_replica_metrics_replica_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_replica_metrics_replica_time ON public.solr_replica_metrics USING btree (replica_id, collected_at DESC);


--
-- Name: idx_solr_collections_cluster; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solr_collections_cluster ON public.solr_collections USING btree (cluster_id);


--
-- Name: idx_solr_metrics_cluster_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solr_metrics_cluster_time ON public.solr_metrics USING btree (cluster_id, collected_at DESC);


--
-- Name: idx_solr_metrics_node_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solr_metrics_node_time ON public.solr_metrics USING btree (node_id, collected_at DESC);


--
-- Name: idx_solr_replicas_node; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solr_replicas_node ON public.solr_replicas USING btree (node_name);


--
-- Name: idx_solr_replicas_shard; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solr_replicas_shard ON public.solr_replicas USING btree (shard_id);


--
-- Name: idx_solr_request_metrics_handler_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solr_request_metrics_handler_time ON public.solr_request_metrics USING btree (handler, collected_at DESC);


--
-- Name: idx_solr_request_metrics_replica_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solr_request_metrics_replica_time ON public.solr_request_metrics USING btree (replica_id, collected_at DESC);


--
-- Name: idx_solr_shards_collection; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_solr_shards_collection ON public.solr_shards USING btree (collection_id);


--
-- Name: nodes nodes_cluster_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nodes
    ADD CONSTRAINT nodes_cluster_id_fkey FOREIGN KEY (cluster_id) REFERENCES public.clusters(id) ON DELETE CASCADE;


--
-- Name: solr_collections solr_collections_cluster_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_collections
    ADD CONSTRAINT solr_collections_cluster_id_fkey FOREIGN KEY (cluster_id) REFERENCES public.clusters(id) ON DELETE CASCADE;


--
-- Name: solr_metrics solr_metrics_cluster_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_metrics
    ADD CONSTRAINT solr_metrics_cluster_id_fkey FOREIGN KEY (cluster_id) REFERENCES public.clusters(id) ON DELETE CASCADE;


--
-- Name: solr_metrics solr_metrics_node_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_metrics
    ADD CONSTRAINT solr_metrics_node_id_fkey FOREIGN KEY (node_id) REFERENCES public.nodes(id) ON DELETE CASCADE;


--
-- Name: solr_replica_metrics solr_replica_metrics_replica_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_replica_metrics
    ADD CONSTRAINT solr_replica_metrics_replica_id_fkey FOREIGN KEY (replica_id) REFERENCES public.solr_replicas(id) ON DELETE CASCADE;


--
-- Name: solr_replicas solr_replicas_shard_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_replicas
    ADD CONSTRAINT solr_replicas_shard_id_fkey FOREIGN KEY (shard_id) REFERENCES public.solr_shards(id) ON DELETE CASCADE;


--
-- Name: solr_request_metrics solr_request_metrics_replica_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_request_metrics
    ADD CONSTRAINT solr_request_metrics_replica_id_fkey FOREIGN KEY (replica_id) REFERENCES public.solr_replicas(id) ON DELETE CASCADE;


--
-- Name: solr_shards solr_shards_collection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.solr_shards
    ADD CONSTRAINT solr_shards_collection_id_fkey FOREIGN KEY (collection_id) REFERENCES public.solr_collections(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict IMpgk4uqrUxKNPdRTY2Cag2hi17wuM5OYpDt3f4F1bbPZZGtxRlGGamPnSpWdhx

