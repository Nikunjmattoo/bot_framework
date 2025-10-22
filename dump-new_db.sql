--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5

-- Started on 2025-10-21 23:24:27

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

--
-- TOC entry 7 (class 2615 OID 58410)
-- Name: public; Type: SCHEMA; Schema: -; Owner: postgres
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO postgres;

--
-- TOC entry 5114 (class 0 OID 0)
-- Dependencies: 7
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: postgres
--

COMMENT ON SCHEMA public IS '';


--
-- TOC entry 2 (class 3079 OID 58413)
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- TOC entry 5116 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- TOC entry 3 (class 3079 OID 58450)
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- TOC entry 5117 (class 0 OID 0)
-- Dependencies: 3
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- TOC entry 288 (class 1255 OID 58461)
-- Name: get_actor_subject(uuid, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.get_actor_subject(p_user_id uuid, p_instance_id uuid) RETURNS jsonb
    LANGUAGE sql STABLE
    AS $$
  SELECT jsonb_build_object(
    'actor', jsonb_build_object(
      'user_id', vas.user_id::text,
      'name',    vas.actor_name,
      'role',    vas.actor_role
    ),
    'subject', jsonb_build_object(
      'mode', vas.subject_mode,
      /* user_id:
         - self / on_behalf_of -> actor user_id (API calls via actor)
         - linked              -> subject_accounts.subject_user_id
      */
      'user_id',
        CASE WHEN vas.subject_mode = 'linked'
             THEN vas.subject_user_id::text
             ELSE vas.user_id::text
        END,
      'type',         COALESCE(vas.subject_type, 'profile'),
      'display_name', COALESCE(vas.display_name, vas.actor_name),
      'subject_id',   vas.subject_id::text  -- UUID handle from subject_accounts
    ),
    'needs', COALESCE(vas.needs, jsonb_build_object('need_role', false, 'need_subject', false))
  )
  FROM v_active_subject vas
  WHERE vas.user_id = p_user_id
    AND (vas.instance_id = p_instance_id OR p_instance_id IS NULL);
$$;


ALTER FUNCTION public.get_actor_subject(p_user_id uuid, p_instance_id uuid) OWNER TO postgres;

--
-- TOC entry 289 (class 1255 OID 58462)
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.set_updated_at() OWNER TO postgres;

--
-- TOC entry 290 (class 1255 OID 58463)
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 220 (class 1259 OID 152551)
-- Name: brands; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.brands (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying NOT NULL,
    phone_number character varying,
    website character varying,
    extra_config jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.brands OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 152590)
-- Name: idempotency_locks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.idempotency_locks (
    id uuid NOT NULL,
    request_id character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.idempotency_locks OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 152657)
-- Name: instance_configs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.instance_configs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    instance_id uuid NOT NULL,
    template_set_id character varying(100) NOT NULL,
    temperature double precision DEFAULT '0.7'::double precision NOT NULL,
    timeout_ms integer DEFAULT 15000 NOT NULL,
    session_timeout_seconds integer DEFAULT 300 NOT NULL,
    use_rag boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.instance_configs OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 152620)
-- Name: instances; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.instances (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    brand_id uuid NOT NULL,
    name character varying NOT NULL,
    channel character varying NOT NULL,
    recipient_number character varying(32),
    is_active boolean DEFAULT true NOT NULL,
    accept_guest_users boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.instances OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 152564)
-- Name: llm_models; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.llm_models (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying NOT NULL,
    provider character varying,
    max_tokens integer NOT NULL,
    details jsonb DEFAULT '{}'::jsonb,
    api_model_name character varying(255),
    temperature numeric(3,2) DEFAULT 0.7,
    input_price_per_1k numeric(10,6),
    output_price_per_1k numeric(10,6),
    currency character varying(3) DEFAULT 'USD'::character varying,
    pricing_updated_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.llm_models OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 152704)
-- Name: messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    session_id uuid NOT NULL,
    user_id uuid,
    instance_id uuid,
    role character varying,
    content text,
    created_at timestamp with time zone,
    topic_paths jsonb DEFAULT '[]'::jsonb NOT NULL,
    processed boolean,
    request_id text,
    turn_number integer,
    trace_id text,
    metadata_json jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.messages OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 152730)
-- Name: session_token_usage; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.session_token_usage (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    session_id uuid NOT NULL,
    template_key character varying(100) NOT NULL,
    function_name character varying(100) NOT NULL,
    planned_tokens integer NOT NULL,
    sent_tokens integer NOT NULL,
    received_tokens integer NOT NULL,
    total_tokens integer NOT NULL,
    llm_model_id uuid,
    input_price_per_1k numeric(10,6),
    output_price_per_1k numeric(10,6),
    cost_usd numeric(10,6),
    currency character varying(3) DEFAULT 'USD'::character varying,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.session_token_usage OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 152682)
-- Name: sessions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    instance_id uuid,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    active boolean DEFAULT true NOT NULL,
    source character varying,
    last_message_at timestamp with time zone,
    last_assistant_message_at timestamp with time zone,
    current_turn integer DEFAULT 0 NOT NULL,
    rollup_cursor_at timestamp with time zone,
    token_plan_json jsonb,
    session_summary text,
    active_task_name character varying(255),
    active_task_status character varying(50),
    next_narrative text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.sessions OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 152579)
-- Name: template_sets; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.template_sets (
    id character varying(100) NOT NULL,
    name character varying(200) NOT NULL,
    description text,
    functions jsonb DEFAULT '{}'::jsonb NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.template_sets OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 152637)
-- Name: templates; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.templates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    template_key character varying(100) NOT NULL,
    name character varying(200) NOT NULL,
    description text,
    sections jsonb DEFAULT '[]'::jsonb NOT NULL,
    llm_model_id uuid,
    version character varying(20) DEFAULT '1.0'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.templates OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 152598)
-- Name: user_identifiers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_identifiers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    brand_id uuid,
    identifier_type character varying(50) NOT NULL,
    identifier_value character varying(500) NOT NULL,
    channel character varying(50) NOT NULL,
    verified boolean DEFAULT false NOT NULL,
    verified_via text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_identifiers OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 152536)
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    acquisition_channel character varying,
    referred_by_user_id uuid,
    user_tier character varying,
    trust_score numeric,
    is_internal_tester boolean,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.users OWNER TO postgres;

--
-- TOC entry 5098 (class 0 OID 152551)
-- Dependencies: 220
-- Data for Name: brands; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.brands (id, name, phone_number, website, extra_config, created_at, updated_at) FROM stdin;
739c280b-0c68-418a-a902-f4bb42da6b2e	Acme Corporation	+19876543210	https://acme-corp.example.com	{}	2025-10-20 13:18:22.892316+05:30	2025-10-20 13:18:22.892319+05:30
9a4ce067-65e1-4250-a61e-4d0f045bdafe	TechStart Inc	+15551234567	https://techstart.example.com	{}	2025-10-20 13:18:22.894298+05:30	2025-10-20 13:18:22.894299+05:30
\.


--
-- TOC entry 5101 (class 0 OID 152590)
-- Dependencies: 223
-- Data for Name: idempotency_locks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.idempotency_locks (id, request_id, created_at) FROM stdin;
\.


--
-- TOC entry 5105 (class 0 OID 152657)
-- Dependencies: 227
-- Data for Name: instance_configs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.instance_configs (id, instance_id, template_set_id, temperature, timeout_ms, session_timeout_seconds, use_rag, is_active, created_at, updated_at) FROM stdin;
e177d6a4-fd05-4773-81c1-268b6c7745fc	6d591095-51ce-4d90-9a34-d38a543b2445	retail-v1	0.7	15000	3600	f	t	2025-10-20 13:18:22.925708+05:30	2025-10-20 13:18:22.925713+05:30
f9d3ca49-eec6-4cdc-9df0-ca1379859514	c7970ca6-627c-4aba-b497-c0acb28bd36e	retail-v1	0.7	15000	3600	f	t	2025-10-20 13:18:22.931496+05:30	2025-10-20 13:18:22.931498+05:30
816adee8-4557-4435-a230-3c5395cdb484	8c654aae-a458-42cf-bbb4-6716d3f76350	retail-v1	0.7	15000	3600	f	t	2025-10-20 13:18:22.934705+05:30	2025-10-20 13:18:22.934707+05:30
0891ead1-4926-4697-a669-c8a1ff5764bd	108b3e46-e27a-4fcc-b0d1-b44728b19d46	retail-v1	0.7	15000	3600	f	t	2025-10-20 13:18:22.937704+05:30	2025-10-20 13:18:22.937706+05:30
\.


--
-- TOC entry 5103 (class 0 OID 152620)
-- Dependencies: 225
-- Data for Name: instances; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.instances (id, brand_id, name, channel, recipient_number, is_active, accept_guest_users, created_at, updated_at) FROM stdin;
6d591095-51ce-4d90-9a34-d38a543b2445	739c280b-0c68-418a-a902-f4bb42da6b2e	Acme Web Chat	web	\N	t	t	2025-10-20 13:18:22.92163+05:30	2025-10-20 13:18:22.921632+05:30
c7970ca6-627c-4aba-b497-c0acb28bd36e	739c280b-0c68-418a-a902-f4bb42da6b2e	Acme WhatsApp Bot	whatsapp	+19876543210	t	t	2025-10-20 13:18:22.929968+05:30	2025-10-20 13:18:22.929971+05:30
8c654aae-a458-42cf-bbb4-6716d3f76350	9a4ce067-65e1-4250-a61e-4d0f045bdafe	TechStart Mobile App	app	\N	t	t	2025-10-20 13:18:22.933297+05:30	2025-10-20 13:18:22.933299+05:30
108b3e46-e27a-4fcc-b0d1-b44728b19d46	9a4ce067-65e1-4250-a61e-4d0f045bdafe	TechStart API	api	\N	t	t	2025-10-20 13:18:22.936293+05:30	2025-10-20 13:18:22.936295+05:30
\.


--
-- TOC entry 5099 (class 0 OID 152564)
-- Dependencies: 221
-- Data for Name: llm_models; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.llm_models (id, name, provider, max_tokens, details, api_model_name, temperature, input_price_per_1k, output_price_per_1k, currency, pricing_updated_at, created_at, updated_at) FROM stdin;
074974b0-9c5c-4bb5-b49f-d4948f55fe3a	GPT-4 Turbo	openai	128000	{}	gpt-4-turbo-preview	0.70	0.010000	0.030000	USD	2025-10-20 13:18:22.879068+05:30	2025-10-20 13:18:22.87907+05:30	2025-10-20 13:18:22.87907+05:30
6e2ebda2-c365-4fc4-9500-ebfc603386f1	GPT-4	openai	8192	{}	gpt-4	0.70	0.030000	0.060000	USD	2025-10-20 13:18:22.880819+05:30	2025-10-20 13:18:22.880821+05:30	2025-10-20 13:18:22.880822+05:30
f4f870b9-3b22-4ca8-be4e-82c7bcd25e97	GPT-3.5 Turbo	openai	16385	{}	gpt-3.5-turbo	0.70	0.000500	0.001500	USD	2025-10-20 13:18:22.881684+05:30	2025-10-20 13:18:22.881686+05:30	2025-10-20 13:18:22.881686+05:30
0c2eaf47-8e44-4649-a8e4-f1c59e38acc6	Claude 3 Opus	anthropic	200000	{}	claude-3-opus-20240229	0.70	0.015000	0.075000	USD	2025-10-20 13:18:22.882825+05:30	2025-10-20 13:18:22.882827+05:30	2025-10-20 13:18:22.882828+05:30
62885d9b-35af-425f-978b-ee522c783fc1	Claude 3 Sonnet	anthropic	200000	{}	claude-3-sonnet-20240229	0.70	0.003000	0.015000	USD	2025-10-20 13:18:22.883794+05:30	2025-10-20 13:18:22.883796+05:30	2025-10-20 13:18:22.883796+05:30
61102816-922f-435c-9aab-7b18e25ff53f	Claude 3.5 Sonnet	anthropic	200000	{}	claude-3-5-sonnet-20241022	0.70	0.003000	0.015000	USD	2025-10-20 13:18:22.884676+05:30	2025-10-20 13:18:22.884677+05:30	2025-10-20 13:18:22.884678+05:30
c149b97f-e550-4420-86e7-e4ab32fc1008	Claude 3 Haiku	anthropic	200000	{}	claude-3-haiku-20240307	0.70	0.000250	0.001250	USD	2025-10-20 13:18:22.885403+05:30	2025-10-20 13:18:22.885404+05:30	2025-10-20 13:18:22.885404+05:30
97642b71-991d-49fe-b58f-197c2f33bd9b	Llama 3.1 70B (Groq)	groq	131072	{}	llama-3.1-70b-versatile	0.70	0.000590	0.000790	USD	2025-10-20 13:18:22.886055+05:30	2025-10-20 13:18:22.886056+05:30	2025-10-20 13:18:22.886056+05:30
fba7d0a3-9dca-4346-8d69-68e02b421306	Llama 3.1 8B (Groq)	groq	131072	{}	llama-3.1-8b-instant	0.70	0.000050	0.000080	USD	2025-10-20 13:18:22.886689+05:30	2025-10-20 13:18:22.88669+05:30	2025-10-20 13:18:22.88669+05:30
deaede43-7e68-4329-b0da-a001334b9b84	Mixtral 8x7B (Groq)	groq	32768	{}	mixtral-8x7b-32768	0.70	0.000240	0.000240	USD	2025-10-20 13:18:22.888327+05:30	2025-10-20 13:18:22.888336+05:30	2025-10-20 13:18:22.888336+05:30
9ef0253e-90ea-468f-9fce-9160488513cd	Gemma 7B (Groq)	groq	8192	{}	gemma-7b-it	0.70	0.000070	0.000070	USD	2025-10-20 13:18:22.889671+05:30	2025-10-20 13:18:22.889672+05:30	2025-10-20 13:18:22.889673+05:30
\.


--
-- TOC entry 5107 (class 0 OID 152704)
-- Dependencies: 229
-- Data for Name: messages; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.messages (id, session_id, user_id, instance_id, role, content, created_at, topic_paths, processed, request_id, turn_number, trace_id, metadata_json, updated_at) FROM stdin;
\.


--
-- TOC entry 5108 (class 0 OID 152730)
-- Dependencies: 230
-- Data for Name: session_token_usage; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.session_token_usage (id, session_id, template_key, function_name, planned_tokens, sent_tokens, received_tokens, total_tokens, llm_model_id, input_price_per_1k, output_price_per_1k, cost_usd, currency, "timestamp", created_at) FROM stdin;
\.


--
-- TOC entry 5106 (class 0 OID 152682)
-- Dependencies: 228
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sessions (id, user_id, instance_id, started_at, ended_at, active, source, last_message_at, last_assistant_message_at, current_turn, rollup_cursor_at, token_plan_json, session_summary, active_task_name, active_task_status, next_narrative, created_at, updated_at) FROM stdin;
5b1807eb-c287-454b-941a-8c2a302c1721	b256ae86-23e0-484f-a290-7cabbce33bc3	6d591095-51ce-4d90-9a34-d38a543b2445	2025-10-20 13:18:22.941296+05:30	\N	t	web	2025-10-20 13:18:22.941299+05:30	\N	0	\N	\N	\N	\N	\N	\N	2025-10-20 13:18:22.941301+05:30	2025-10-20 13:18:22.941301+05:30
b1345137-323d-4e4e-88eb-e5e03d2351e6	9fbced52-1ff0-4958-9573-44423e442f5a	6d591095-51ce-4d90-9a34-d38a543b2445	2025-10-20 13:18:22.944181+05:30	\N	t	web	2025-10-20 13:18:22.944199+05:30	\N	0	\N	\N	\N	\N	\N	\N	2025-10-20 13:18:22.9442+05:30	2025-10-20 13:18:22.944201+05:30
f575ab63-0a73-4c76-92ff-d5adc5452070	34ed2c6d-16f8-43b9-8813-392858d38846	6d591095-51ce-4d90-9a34-d38a543b2445	2025-10-20 13:18:22.9457+05:30	\N	t	web	2025-10-20 13:18:22.945702+05:30	\N	0	\N	\N	\N	\N	\N	\N	2025-10-20 13:18:22.945704+05:30	2025-10-20 13:18:22.945704+05:30
\.


--
-- TOC entry 5100 (class 0 OID 152579)
-- Dependencies: 222
-- Data for Name: template_sets; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.template_sets (id, name, description, functions, is_active, created_at, updated_at) FROM stdin;
retail-v1	Retail Template Set V1	Standard retail conversation templates	{"intent": "intent_v1", "compose": "response_v1"}	t	2025-10-20 13:18:22.912889+05:30	2025-10-20 13:18:22.912891+05:30
\.


--
-- TOC entry 5104 (class 0 OID 152637)
-- Dependencies: 226
-- Data for Name: templates; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.templates (id, template_key, name, description, sections, llm_model_id, version, is_active, created_at, updated_at) FROM stdin;
fc890a8d-5977-4bff-aa52-3f148505c7ca	response_v1	Response Template V1	Standard response generation template	[{"key": "system_instructions", "type": "static", "sequence": 1, "budget_tokens": 500}, {"key": "conversation_history", "type": "dynamic", "sequence": 2, "budget_tokens": 2000}, {"key": "user_message", "type": "dynamic", "sequence": 3, "budget_tokens": 500}]	6e2ebda2-c365-4fc4-9500-ebfc603386f1	1.0	t	2025-10-20 13:18:22.914775+05:30	2025-10-20 13:18:22.914777+05:30
24753f1e-ac8c-45c3-847d-0ad83f146902	intent_v1	Intent Classification V1	Intent detection template	[{"key": "system_instructions", "type": "static", "sequence": 1, "budget_tokens": 300}, {"key": "user_message", "type": "dynamic", "sequence": 2, "budget_tokens": 200}]	6e2ebda2-c365-4fc4-9500-ebfc603386f1	1.0	t	2025-10-20 13:18:22.91638+05:30	2025-10-20 13:18:22.916383+05:30
\.


--
-- TOC entry 5102 (class 0 OID 152598)
-- Dependencies: 224
-- Data for Name: user_identifiers; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_identifiers (id, user_id, brand_id, identifier_type, identifier_value, channel, verified, verified_via, created_at, updated_at) FROM stdin;
bb465b96-79e2-4818-ab96-743b1ab7005a	b256ae86-23e0-484f-a290-7cabbce33bc3	739c280b-0c68-418a-a902-f4bb42da6b2e	phone_e164	+15551234567	web	t	seed_script	2025-10-20 13:18:22.897993+05:30	2025-10-20 13:18:22.897994+05:30
9d410623-3d20-48ce-8a10-5cc5f1538011	b256ae86-23e0-484f-a290-7cabbce33bc3	739c280b-0c68-418a-a902-f4bb42da6b2e	email	john.doe@example.com	web	t	seed_script	2025-10-20 13:18:22.899598+05:30	2025-10-20 13:18:22.8996+05:30
119bbde0-f928-47d0-905a-39d6d7f5ae8e	b256ae86-23e0-484f-a290-7cabbce33bc3	9a4ce067-65e1-4250-a61e-4d0f045bdafe	phone_e164	+15551234567	web	t	seed_script	2025-10-20 13:18:22.900803+05:30	2025-10-20 13:18:22.900805+05:30
9bcb0fc5-d0b4-40a8-a350-ed16dfa6c39b	b256ae86-23e0-484f-a290-7cabbce33bc3	9a4ce067-65e1-4250-a61e-4d0f045bdafe	email	john.doe@example.com	web	t	seed_script	2025-10-20 13:18:22.901956+05:30	2025-10-20 13:18:22.901958+05:30
74996092-e3e9-43fd-956c-a47f2d453a8c	9fbced52-1ff0-4958-9573-44423e442f5a	739c280b-0c68-418a-a902-f4bb42da6b2e	phone_e164	+15559876543	whatsapp	t	seed_script	2025-10-20 13:18:22.903775+05:30	2025-10-20 13:18:22.903777+05:30
d2124400-f682-4461-b5f4-87609e43dfaa	9fbced52-1ff0-4958-9573-44423e442f5a	9a4ce067-65e1-4250-a61e-4d0f045bdafe	phone_e164	+15559876543	whatsapp	t	seed_script	2025-10-20 13:18:22.904605+05:30	2025-10-20 13:18:22.904606+05:30
2aa245d9-a81a-404f-8e41-b247c9f3437b	34ed2c6d-16f8-43b9-8813-392858d38846	739c280b-0c68-418a-a902-f4bb42da6b2e	phone_e164	+15555555555	app	t	seed_script	2025-10-20 13:18:22.90635+05:30	2025-10-20 13:18:22.906351+05:30
0ef0159e-c73d-419f-a3db-2bec7e90e3ae	34ed2c6d-16f8-43b9-8813-392858d38846	739c280b-0c68-418a-a902-f4bb42da6b2e	email	jane.smith@example.com	app	t	seed_script	2025-10-20 13:18:22.907272+05:30	2025-10-20 13:18:22.907275+05:30
98345ccc-da49-4090-bab4-f1da466db792	34ed2c6d-16f8-43b9-8813-392858d38846	739c280b-0c68-418a-a902-f4bb42da6b2e	device_id	device-abc-123-xyz	app	t	seed_script	2025-10-20 13:18:22.908272+05:30	2025-10-20 13:18:22.908274+05:30
d112e5cb-b0ab-4cc3-944c-dcb386ea9457	34ed2c6d-16f8-43b9-8813-392858d38846	9a4ce067-65e1-4250-a61e-4d0f045bdafe	phone_e164	+15555555555	app	t	seed_script	2025-10-20 13:18:22.909127+05:30	2025-10-20 13:18:22.909128+05:30
55c0d494-57e5-48d1-9bc2-21a9bfb0c684	34ed2c6d-16f8-43b9-8813-392858d38846	9a4ce067-65e1-4250-a61e-4d0f045bdafe	email	jane.smith@example.com	app	t	seed_script	2025-10-20 13:18:22.90994+05:30	2025-10-20 13:18:22.909941+05:30
21fede2c-76c5-46b8-a055-56e838cc6ef6	34ed2c6d-16f8-43b9-8813-392858d38846	9a4ce067-65e1-4250-a61e-4d0f045bdafe	device_id	device-abc-123-xyz	app	t	seed_script	2025-10-20 13:18:22.910556+05:30	2025-10-20 13:18:22.910557+05:30
\.


--
-- TOC entry 5097 (class 0 OID 152536)
-- Dependencies: 219
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, acquisition_channel, referred_by_user_id, user_tier, trust_score, is_internal_tester, created_at, updated_at) FROM stdin;
b256ae86-23e0-484f-a290-7cabbce33bc3	web	\N	standard	\N	f	2025-10-20 13:18:22.89658+05:30	2025-10-20 13:18:22.896582+05:30
9fbced52-1ff0-4958-9573-44423e442f5a	whatsapp	\N	verified	\N	f	2025-10-20 13:18:22.903015+05:30	2025-10-20 13:18:22.903016+05:30
34ed2c6d-16f8-43b9-8813-392858d38846	app	\N	premium	\N	f	2025-10-20 13:18:22.905578+05:30	2025-10-20 13:18:22.905579+05:30
77cb94fe-85bf-4912-a189-3d58a6610842	web	\N	guest	\N	f	2025-10-20 13:18:22.911258+05:30	2025-10-20 13:18:22.91126+05:30
44c2bb07-27ed-4db7-9ef8-697dd4f594bd	test	\N	\N	\N	\N	2025-10-21 19:38:58.078598+05:30	2025-10-21 19:38:58.078598+05:30
54ca470e-50e3-474d-9ce5-9f391671f744	test	\N	\N	\N	\N	2025-10-21 19:41:04.522024+05:30	2025-10-21 19:41:04.522024+05:30
36bf985d-991d-476a-b43a-bd6f78f44a45	test	\N	premium	\N	\N	2025-10-21 19:41:04.537915+05:30	2025-10-21 19:41:04.540586+05:30
2f9146c4-90d3-473a-ab6e-76ab4b3a140e	test	\N	standard	\N	\N	2025-10-21 19:41:04.563615+05:30	2025-10-21 19:41:04.563615+05:30
acdd12f5-5d30-44b5-ac9d-9947d28f7fb7	test	\N	\N	\N	\N	2025-10-21 19:42:08.982298+05:30	2025-10-21 19:42:08.982298+05:30
b71d5779-e9bf-41af-be9b-68b5744b159b	test	\N	premium	\N	\N	2025-10-21 19:42:08.99833+05:30	2025-10-21 19:42:09.001121+05:30
86018a6a-1ceb-429c-a8d9-fd853bd22c20	test	\N	standard	\N	\N	2025-10-21 19:42:09.013697+05:30	2025-10-21 19:42:09.013697+05:30
47e0ff43-7f69-4851-9902-e209a82e1ef5	test	\N	\N	\N	\N	2025-10-21 19:47:50.302149+05:30	2025-10-21 19:47:50.302149+05:30
358b2ec2-b4fe-46db-ade8-efaa476cd862	test	\N	premium	\N	\N	2025-10-21 19:47:50.315194+05:30	2025-10-21 19:47:50.317161+05:30
53ab2ef3-1d78-4d81-8a40-2d2d3257c2b8	test	\N	standard	\N	\N	2025-10-21 19:47:50.328311+05:30	2025-10-21 19:47:50.328311+05:30
a8ff959c-7513-46b3-ad84-b8b5a12c2316	test	\N	\N	\N	\N	2025-10-21 19:51:35.841259+05:30	2025-10-21 19:51:35.841259+05:30
cd1f4c73-6b3b-4085-9cc2-4021dd5a1ed4	test	\N	\N	\N	\N	2025-10-21 23:22:43.170421+05:30	2025-10-21 23:22:43.170421+05:30
\.


--
-- TOC entry 4892 (class 2606 OID 152563)
-- Name: brands brands_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT brands_name_key UNIQUE (name);


--
-- TOC entry 4894 (class 2606 OID 152561)
-- Name: brands brands_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.brands
    ADD CONSTRAINT brands_pkey PRIMARY KEY (id);


--
-- TOC entry 4902 (class 2606 OID 152596)
-- Name: idempotency_locks idempotency_locks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.idempotency_locks
    ADD CONSTRAINT idempotency_locks_pkey PRIMARY KEY (id);


--
-- TOC entry 4915 (class 2606 OID 152671)
-- Name: instance_configs instance_configs_instance_id_is_active_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instance_configs
    ADD CONSTRAINT instance_configs_instance_id_is_active_key UNIQUE (instance_id, is_active);


--
-- TOC entry 4917 (class 2606 OID 152669)
-- Name: instance_configs instance_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instance_configs
    ADD CONSTRAINT instance_configs_pkey PRIMARY KEY (id);


--
-- TOC entry 4909 (class 2606 OID 152631)
-- Name: instances instances_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (id);


--
-- TOC entry 4896 (class 2606 OID 152578)
-- Name: llm_models llm_models_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.llm_models
    ADD CONSTRAINT llm_models_name_key UNIQUE (name);


--
-- TOC entry 4898 (class 2606 OID 152576)
-- Name: llm_models llm_models_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.llm_models
    ADD CONSTRAINT llm_models_pkey PRIMARY KEY (id);


--
-- TOC entry 4925 (class 2606 OID 152714)
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- TOC entry 4927 (class 2606 OID 152738)
-- Name: session_token_usage session_token_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_token_usage
    ADD CONSTRAINT session_token_usage_pkey PRIMARY KEY (id);


--
-- TOC entry 4921 (class 2606 OID 152693)
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- TOC entry 4900 (class 2606 OID 152589)
-- Name: template_sets template_sets_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.template_sets
    ADD CONSTRAINT template_sets_pkey PRIMARY KEY (id);


--
-- TOC entry 4911 (class 2606 OID 152649)
-- Name: templates templates_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.templates
    ADD CONSTRAINT templates_pkey PRIMARY KEY (id);


--
-- TOC entry 4913 (class 2606 OID 152651)
-- Name: templates templates_template_key_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.templates
    ADD CONSTRAINT templates_template_key_key UNIQUE (template_key);


--
-- TOC entry 4907 (class 2606 OID 152608)
-- Name: user_identifiers user_identifiers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_identifiers
    ADD CONSTRAINT user_identifiers_pkey PRIMARY KEY (id);


--
-- TOC entry 4890 (class 2606 OID 152545)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- TOC entry 4922 (class 1259 OID 152749)
-- Name: idx_messages_session_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_session_id ON public.messages USING btree (session_id);


--
-- TOC entry 4923 (class 1259 OID 152750)
-- Name: idx_messages_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_user_id ON public.messages USING btree (user_id);


--
-- TOC entry 4918 (class 1259 OID 152751)
-- Name: idx_sessions_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sessions_active ON public.sessions USING btree (active) WHERE (active = true);


--
-- TOC entry 4919 (class 1259 OID 152752)
-- Name: idx_sessions_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_sessions_user_id ON public.sessions USING btree (user_id);


--
-- TOC entry 4904 (class 1259 OID 152753)
-- Name: idx_user_identifiers_lookup; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_user_identifiers_lookup ON public.user_identifiers USING btree (identifier_type, identifier_value, channel);


--
-- TOC entry 4903 (class 1259 OID 152597)
-- Name: ix_idempotency_locks_request_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_idempotency_locks_request_id ON public.idempotency_locks USING btree (request_id);


--
-- TOC entry 4905 (class 1259 OID 152619)
-- Name: user_identifiers_brand_scoped_key; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX user_identifiers_brand_scoped_key ON public.user_identifiers USING btree (identifier_type, identifier_value, channel, brand_id) WHERE (brand_id IS NOT NULL);


--
-- TOC entry 4943 (class 2620 OID 152756)
-- Name: brands update_brands_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_brands_updated_at BEFORE UPDATE ON public.brands FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4949 (class 2620 OID 152761)
-- Name: instance_configs update_instance_configs_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_instance_configs_updated_at BEFORE UPDATE ON public.instance_configs FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4947 (class 2620 OID 152760)
-- Name: instances update_instances_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_instances_updated_at BEFORE UPDATE ON public.instances FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4944 (class 2620 OID 152757)
-- Name: llm_models update_llm_models_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_llm_models_updated_at BEFORE UPDATE ON public.llm_models FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4951 (class 2620 OID 152763)
-- Name: messages update_messages_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_messages_updated_at BEFORE UPDATE ON public.messages FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4950 (class 2620 OID 152762)
-- Name: sessions update_sessions_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON public.sessions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4945 (class 2620 OID 152758)
-- Name: template_sets update_template_sets_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_template_sets_updated_at BEFORE UPDATE ON public.template_sets FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4948 (class 2620 OID 152759)
-- Name: templates update_templates_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_templates_updated_at BEFORE UPDATE ON public.templates FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4946 (class 2620 OID 152755)
-- Name: user_identifiers update_user_identifiers_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_user_identifiers_updated_at BEFORE UPDATE ON public.user_identifiers FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4942 (class 2620 OID 152754)
-- Name: users update_users_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- TOC entry 4933 (class 2606 OID 152672)
-- Name: instance_configs instance_configs_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instance_configs
    ADD CONSTRAINT instance_configs_instance_id_fkey FOREIGN KEY (instance_id) REFERENCES public.instances(id) ON DELETE CASCADE;


--
-- TOC entry 4934 (class 2606 OID 152677)
-- Name: instance_configs instance_configs_template_set_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instance_configs
    ADD CONSTRAINT instance_configs_template_set_id_fkey FOREIGN KEY (template_set_id) REFERENCES public.template_sets(id);


--
-- TOC entry 4931 (class 2606 OID 152632)
-- Name: instances instances_brand_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.instances
    ADD CONSTRAINT instances_brand_id_fkey FOREIGN KEY (brand_id) REFERENCES public.brands(id) ON DELETE CASCADE;


--
-- TOC entry 4937 (class 2606 OID 152725)
-- Name: messages messages_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_instance_id_fkey FOREIGN KEY (instance_id) REFERENCES public.instances(id);


--
-- TOC entry 4938 (class 2606 OID 152715)
-- Name: messages messages_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(id) ON DELETE CASCADE;


--
-- TOC entry 4939 (class 2606 OID 152720)
-- Name: messages messages_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 4940 (class 2606 OID 152744)
-- Name: session_token_usage session_token_usage_llm_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_token_usage
    ADD CONSTRAINT session_token_usage_llm_model_id_fkey FOREIGN KEY (llm_model_id) REFERENCES public.llm_models(id) ON DELETE SET NULL;


--
-- TOC entry 4941 (class 2606 OID 152739)
-- Name: session_token_usage session_token_usage_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.session_token_usage
    ADD CONSTRAINT session_token_usage_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.sessions(id) ON DELETE CASCADE;


--
-- TOC entry 4935 (class 2606 OID 152699)
-- Name: sessions sessions_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_instance_id_fkey FOREIGN KEY (instance_id) REFERENCES public.instances(id) ON DELETE SET NULL;


--
-- TOC entry 4936 (class 2606 OID 152694)
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 4932 (class 2606 OID 152652)
-- Name: templates templates_llm_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.templates
    ADD CONSTRAINT templates_llm_model_id_fkey FOREIGN KEY (llm_model_id) REFERENCES public.llm_models(id);


--
-- TOC entry 4929 (class 2606 OID 152614)
-- Name: user_identifiers user_identifiers_brand_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_identifiers
    ADD CONSTRAINT user_identifiers_brand_id_fkey FOREIGN KEY (brand_id) REFERENCES public.brands(id);


--
-- TOC entry 4930 (class 2606 OID 152609)
-- Name: user_identifiers user_identifiers_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_identifiers
    ADD CONSTRAINT user_identifiers_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 4928 (class 2606 OID 152546)
-- Name: users users_referred_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_referred_by_user_id_fkey FOREIGN KEY (referred_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- TOC entry 5115 (class 0 OID 0)
-- Dependencies: 7
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;


-- Completed on 2025-10-21 23:24:27

--
-- PostgreSQL database dump complete
--

