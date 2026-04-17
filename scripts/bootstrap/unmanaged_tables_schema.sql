--
-- PostgreSQL database dump
--

\restrict WtAegLdqoCboT3MSkkg6xsEQ4H5xWtEzNKdW9qdEUjMNlEzAFZ1gd4VgUmklgrb

-- Dumped from database version 16.13 (Debian 16.13-1.pgdg12+1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-1.pgdg22.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
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
-- Name: course; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.course (
    course_id integer NOT NULL,
    course_code character varying(20) NOT NULL,
    course_name character varying(200),
    instructor_id integer,
    academic_year character varying(20),
    semester character varying(20),
    is_active boolean DEFAULT true,
    created_at timestamp without time zone
);


--
-- Name: course_course_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.course_course_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: course_course_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.course_course_id_seq OWNED BY public.course.course_id;


--
-- Name: enrollment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.enrollment (
    enrollment_id integer NOT NULL,
    user_id integer,
    section_id integer,
    team_id integer,
    enrolled_at timestamp without time zone,
    is_active boolean DEFAULT true,
    onboarding_completed boolean DEFAULT false,
    language character varying(10) DEFAULT 'en'::character varying
);


--
-- Name: enrollment_enrollment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.enrollment_enrollment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: enrollment_enrollment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.enrollment_enrollment_id_seq OWNED BY public.enrollment.enrollment_id;


--
-- Name: grading_component_mapping; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.grading_component_mapping (
    mapping_id integer NOT NULL,
    category_id integer NOT NULL,
    component_key character varying(100) NOT NULL,
    component_weight numeric(5,2) DEFAULT 0 NOT NULL,
    score_transform character varying(50) DEFAULT 'linear'::character varying NOT NULL,
    threshold_value numeric(10,2),
    description text
);


--
-- Name: grading_component_mapping_mapping_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.grading_component_mapping_mapping_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: grading_component_mapping_mapping_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.grading_component_mapping_mapping_id_seq OWNED BY public.grading_component_mapping.mapping_id;


--
-- Name: grading_rubric; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.grading_rubric (
    rubric_id integer NOT NULL,
    course_id integer NOT NULL,
    rubric_name character varying(200) DEFAULT 'Default Rubric'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_by integer,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: grading_rubric_category; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.grading_rubric_category (
    category_id integer NOT NULL,
    rubric_id integer NOT NULL,
    category_name character varying(200) NOT NULL,
    weight numeric(5,2) DEFAULT 0 NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    description text
);


--
-- Name: grading_rubric_category_category_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.grading_rubric_category_category_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: grading_rubric_category_category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.grading_rubric_category_category_id_seq OWNED BY public.grading_rubric_category.category_id;


--
-- Name: grading_rubric_rubric_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.grading_rubric_rubric_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: grading_rubric_rubric_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.grading_rubric_rubric_id_seq OWNED BY public.grading_rubric.rubric_id;


--
-- Name: section; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.section (
    section_id integer NOT NULL,
    course_id integer,
    section_code character varying(20),
    section_name character varying(200),
    max_teams integer DEFAULT 8,
    team_size_min integer DEFAULT 3,
    team_size_max integer DEFAULT 5,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone
);


--
-- Name: section_section_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.section_section_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: section_section_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.section_section_id_seq OWNED BY public.section.section_id;


--
-- Name: simulation_instance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.simulation_instance (
    instance_id integer NOT NULL,
    section_id integer,
    game_id integer,
    current_round integer DEFAULT 0,
    total_rounds integer DEFAULT 10,
    status character varying(20) DEFAULT 'setup'::character varying,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    settings jsonb DEFAULT '{}'::jsonb,
    auto_advance boolean DEFAULT false,
    created_at timestamp without time zone
);


--
-- Name: simulation_instance_instance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.simulation_instance_instance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: simulation_instance_instance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.simulation_instance_instance_id_seq OWNED BY public.simulation_instance.instance_id;


--
-- Name: student_grade_adjustment; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.student_grade_adjustment (
    adjustment_id integer NOT NULL,
    instance_id integer NOT NULL,
    user_id integer NOT NULL,
    team_id integer NOT NULL,
    adjustment_type character varying(100) DEFAULT 'participation'::character varying NOT NULL,
    adjustment_value numeric(6,2) DEFAULT 0 NOT NULL,
    reason text,
    adjusted_by integer,
    created_at timestamp with time zone
);


--
-- Name: student_grade_adjustment_adjustment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.student_grade_adjustment_adjustment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: student_grade_adjustment_adjustment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.student_grade_adjustment_adjustment_id_seq OWNED BY public.student_grade_adjustment.adjustment_id;


--
-- Name: team_grade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_grade (
    grade_id integer NOT NULL,
    instance_id integer NOT NULL,
    team_id integer NOT NULL,
    category_id integer,
    computed_score numeric(6,2),
    override_score numeric(6,2),
    final_score numeric(6,2),
    instructor_comments text,
    graded_by integer,
    graded_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: team_grade_grade_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.team_grade_grade_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: team_grade_grade_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.team_grade_grade_id_seq OWNED BY public.team_grade.grade_id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    username character varying(255) NOT NULL,
    password_hash text,
    role character varying(50),
    team_id integer,
    email character varying(200),
    student_id character varying(50),
    display_name character varying(200)
);


--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- Name: course course_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course ALTER COLUMN course_id SET DEFAULT nextval('public.course_course_id_seq'::regclass);


--
-- Name: enrollment enrollment_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enrollment ALTER COLUMN enrollment_id SET DEFAULT nextval('public.enrollment_enrollment_id_seq'::regclass);


--
-- Name: grading_component_mapping mapping_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_component_mapping ALTER COLUMN mapping_id SET DEFAULT nextval('public.grading_component_mapping_mapping_id_seq'::regclass);


--
-- Name: grading_rubric rubric_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_rubric ALTER COLUMN rubric_id SET DEFAULT nextval('public.grading_rubric_rubric_id_seq'::regclass);


--
-- Name: grading_rubric_category category_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_rubric_category ALTER COLUMN category_id SET DEFAULT nextval('public.grading_rubric_category_category_id_seq'::regclass);


--
-- Name: section section_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.section ALTER COLUMN section_id SET DEFAULT nextval('public.section_section_id_seq'::regclass);


--
-- Name: simulation_instance instance_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulation_instance ALTER COLUMN instance_id SET DEFAULT nextval('public.simulation_instance_instance_id_seq'::regclass);


--
-- Name: student_grade_adjustment adjustment_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_grade_adjustment ALTER COLUMN adjustment_id SET DEFAULT nextval('public.student_grade_adjustment_adjustment_id_seq'::regclass);


--
-- Name: team_grade grade_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_grade ALTER COLUMN grade_id SET DEFAULT nextval('public.team_grade_grade_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- Name: course course_course_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course
    ADD CONSTRAINT course_course_code_key UNIQUE (course_code);


--
-- Name: course course_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.course
    ADD CONSTRAINT course_pkey PRIMARY KEY (course_id);


--
-- Name: enrollment enrollment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enrollment
    ADD CONSTRAINT enrollment_pkey PRIMARY KEY (enrollment_id);


--
-- Name: enrollment enrollment_user_id_section_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enrollment
    ADD CONSTRAINT enrollment_user_id_section_id_key UNIQUE (user_id, section_id);


--
-- Name: grading_component_mapping grading_component_mapping_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_component_mapping
    ADD CONSTRAINT grading_component_mapping_pkey PRIMARY KEY (mapping_id);


--
-- Name: grading_rubric_category grading_rubric_category_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_rubric_category
    ADD CONSTRAINT grading_rubric_category_pkey PRIMARY KEY (category_id);


--
-- Name: grading_rubric grading_rubric_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_rubric
    ADD CONSTRAINT grading_rubric_pkey PRIMARY KEY (rubric_id);


--
-- Name: section section_course_id_section_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.section
    ADD CONSTRAINT section_course_id_section_code_key UNIQUE (course_id, section_code);


--
-- Name: section section_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.section
    ADD CONSTRAINT section_pkey PRIMARY KEY (section_id);


--
-- Name: simulation_instance simulation_instance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulation_instance
    ADD CONSTRAINT simulation_instance_pkey PRIMARY KEY (instance_id);


--
-- Name: simulation_instance simulation_instance_section_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulation_instance
    ADD CONSTRAINT simulation_instance_section_id_key UNIQUE (section_id);


--
-- Name: student_grade_adjustment student_grade_adjustment_instance_id_user_id_adjustment_typ_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_grade_adjustment
    ADD CONSTRAINT student_grade_adjustment_instance_id_user_id_adjustment_typ_key UNIQUE (instance_id, user_id, adjustment_type);


--
-- Name: student_grade_adjustment student_grade_adjustment_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_grade_adjustment
    ADD CONSTRAINT student_grade_adjustment_pkey PRIMARY KEY (adjustment_id);


--
-- Name: team_grade team_grade_instance_id_team_id_category_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_grade
    ADD CONSTRAINT team_grade_instance_id_team_id_category_id_key UNIQUE (instance_id, team_id, category_id);


--
-- Name: team_grade team_grade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_grade
    ADD CONSTRAINT team_grade_pkey PRIMARY KEY (grade_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: enrollment enrollment_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enrollment
    ADD CONSTRAINT enrollment_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.section(section_id);


--
-- Name: enrollment enrollment_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.enrollment
    ADD CONSTRAINT enrollment_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: grading_component_mapping grading_component_mapping_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_component_mapping
    ADD CONSTRAINT grading_component_mapping_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.grading_rubric_category(category_id) ON DELETE CASCADE;


--
-- Name: grading_rubric_category grading_rubric_category_rubric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.grading_rubric_category
    ADD CONSTRAINT grading_rubric_category_rubric_id_fkey FOREIGN KEY (rubric_id) REFERENCES public.grading_rubric(rubric_id) ON DELETE CASCADE;


--
-- Name: section section_course_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.section
    ADD CONSTRAINT section_course_id_fkey FOREIGN KEY (course_id) REFERENCES public.course(course_id);


--
-- Name: simulation_instance simulation_instance_section_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.simulation_instance
    ADD CONSTRAINT simulation_instance_section_id_fkey FOREIGN KEY (section_id) REFERENCES public.section(section_id);


--
-- PostgreSQL database dump complete
--

\unrestrict WtAegLdqoCboT3MSkkg6xsEQ4H5xWtEzNKdW9qdEUjMNlEzAFZ1gd4VgUmklgrb

