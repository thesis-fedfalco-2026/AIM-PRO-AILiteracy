// Generated from services/openapi/authoring.json by
// apps/packages/api-client/scripts/generate.mjs. Do not edit; run
// `npm run generate:client` in apps/ after the snapshot changes.

export interface paths {
    "/auth/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Finish the code flow, map the identity and start a server-side session */
        get: operations["callback_auth_callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Start the OIDC code flow with PKCE at the identity provider */
        get: operations["login_auth_login_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** End the session; the result is the provider logout URL to visit, if any */
        post: operations["logout_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The signed-in subject and the CSRF token for writes */
        get: operations["session_auth_session_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Context summary with the same redaction as the CLI show */
        get: operations["context_summary_contexts__context_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/applications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Apply an approved proposal; a replay of the operation id returns the same change */
        post: operations["apply_contexts__context_id__applications_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/decisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Record a human decision on the reviewed payload; 409 if its key or revision is stale */
        post: operations["decide_contexts__context_id__decisions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/pending-proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Proposals awaiting a decision; none for a learner-only subject, as in show */
        get: operations["pending_proposals_contexts__context_id__pending_proposals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/projects/{project_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Current selections, approval receipts and stale dependencies (CLI show-authoring-project) */
        get: operations["project_inspection_contexts__context_id__projects__project_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/resources/{resource_id}/versions/{version}/project-syllabus": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The approved syllabus of this exact current project revision (CLI show-project-syllabus) */
        get: operations["project_syllabus_contexts__context_id__resources__resource_id__versions__version__project_syllabus_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/contexts/{context_id}/resources/{resource_id}/versions/{version}/release": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Receipts, the exact frozen closure and findings of this release (CLI show-release) */
        get: operations["release_inspection_contexts__context_id__resources__resource_id__versions__version__release_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Liveness; needs no session */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * ApplicationRequest
         * @description Apply an approved proposal, as the CLI ``apply``; ``operation_id`` makes a retry a replay.
         */
        ApplicationRequest: {
            /** Operation Id */
            operation_id: string;
            proposal: components["schemas"]["EntityRef"];
        };
        /** ApprovedSyllabus */
        ApprovedSyllabus: {
            artifact: components["schemas"]["SyllabusArtifact"];
            change: components["schemas"]["EntityRef"];
            decision: components["schemas"]["EntityRef"];
            proposal: components["schemas"]["EntityRef"];
            source: components["schemas"]["LeadInput"];
            syllabus: components["schemas"]["EntityRef"];
        };
        /** ArtifactInspection */
        ArtifactInspection: {
            /** Approval Error */
            approval_error?: string | null;
            receipt?: components["schemas"]["ReviewReceipt"] | null;
            selection: components["schemas"]["ArtifactSelection"];
        };
        /** ArtifactSelection */
        ArtifactSelection: {
            /**
             * Definitions
             * @default []
             */
            definitions: components["schemas"]["EntityRef"][];
            /**
             * Depends On
             * @default []
             */
            depends_on: components["schemas"]["EntityRef"][];
            /** Key */
            key: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "SOURCE" | "SYLLABUS" | "ASSESSMENT" | "TEACHER_CONTENT" | "TRAINER_CONTENT";
            resource: components["schemas"]["EntityRef"];
        };
        /**
         * ContextSummary
         * @description The context, the entities the subject may see and the snapshot findings.
         *
         *     A learner-only subject sees only the context, its own participant record and
         *     its own learning records, never proposals, decisions or other participants.
         */
        ContextSummary: {
            context: components["schemas"]["Entity"];
            /** Entities */
            entities: components["schemas"]["Entity"][];
            /** Findings */
            findings: components["schemas"]["Finding"][];
        };
        /** CorpusCitation */
        CorpusCitation: {
            /** Document Ids */
            document_ids: string[];
            /** Resource Id */
            resource_id: string;
            /** Resource Version */
            resource_version: string;
            /** Supported Claim */
            supported_claim: string;
        };
        /** CorpusDocument */
        CorpusDocument: {
            /** Id */
            id: string;
            /** Metadata */
            metadata: {
                [key: string]: unknown;
            };
            /** Score */
            score: number;
            /** Text */
            text: string;
        };
        /** CorpusEvidence */
        CorpusEvidence: {
            /** K */
            k: number;
            /** Query */
            query: string;
            /** Resources */
            resources: components["schemas"]["CorpusResource"][];
            selection?: components["schemas"]["SourceSelectionSummary"] | null;
            /** Source Scope */
            source_scope: string;
        };
        /** CorpusResource */
        CorpusResource: {
            /** Documents */
            documents: components["schemas"]["CorpusDocument"][];
            /** Identity */
            identity: string;
            /** Licence */
            licence: string;
            /** Source Scope */
            source_scope: string;
            /** Title */
            title: string;
            /** Uri */
            uri: string;
            /** Version */
            version: string;
        };
        /** CoverageRequirement */
        CoverageRequirement: {
            /**
             * Actor
             * @enum {string}
             */
            actor: "FACILITATOR" | "PEER" | "LEARNER";
            /**
             * Expected Intent
             * @enum {string}
             */
            expected_intent: "EXPLAIN" | "PRACTICE" | "ASSESS";
            /** Key */
            key: string;
            /** Required Action */
            required_action: string;
            /**
             * Source Field
             * @enum {string}
             */
            source_field: "description" | "inPractice" | "rationale" | "contextDetails";
            /** Source Object Id */
            source_object_id: string;
            /** Source Quote */
            source_quote: string;
            /** Source Target Id */
            source_target_id: string;
        };
        /**
         * DecisionRequest
         * @description A decision on ``target``, the exact revision the reviewer saw, as the CLI ``decide``.
         */
        DecisionRequest: {
            /**
             * Decision
             * @enum {string}
             */
            decision: "APPROVE" | "REJECT" | "REQUEST_REVISION";
            /** Reason */
            reason: string;
            /** Review Payload Key */
            review_payload_key: string;
            target: components["schemas"]["EntityRef"];
        };
        /** Entity */
        Entity: {
            /** Fields */
            fields: {
                [key: string]: components["schemas"]["JsonValue"];
            };
            /** Id */
            id: string;
            provenance: components["schemas"]["Provenance"];
            /** Type */
            type: string;
            /** Version */
            version: string;
        };
        /** EntityRef */
        EntityRef: {
            /** Id */
            id: string;
            /** Type */
            type: string;
            /** Version */
            version: string;
        };
        /** ErrorBody */
        ErrorBody: {
            /** Detail */
            detail: string | components["schemas"]["ValidationIssue"][];
            /** Error */
            error: string;
            /** Request Id */
            request_id: string;
        };
        /** Finding */
        Finding: {
            /** Code */
            code: string;
            /** Reason */
            reason: string;
            /**
             * Resolution
             * @default Correct the data or provide the required configuration.
             */
            resolution: string;
            /**
             * Severity
             * @default BLOCKING
             * @enum {string}
             */
            severity: "BLOCKING" | "WARNING" | "INFORMATION";
            /** Target */
            target: string;
        };
        /** HealthView */
        HealthView: {
            /**
             * Status
             * @constant
             */
            status: "ok";
        };
        JsonValue: unknown;
        /** LeadInput */
        LeadInput: {
            /** Conforms To Generated Contracts */
            conforms_to_generated_contracts: boolean;
            corpus_evidence?: components["schemas"]["CorpusEvidence"] | null;
            /** Domain Schemas */
            domain_schemas: {
                [key: string]: {
                    [key: string]: unknown;
                };
            };
            /** Findings */
            findings: {
                [key: string]: unknown;
            }[];
            /** Metamodel Fingerprint */
            metamodel_fingerprint: string;
            /**
             * Purpose
             * @default AUTHORING_REVIEW
             * @constant
             */
            purpose: "AUTHORING_REVIEW";
            source: components["schemas"]["ScenarioInput"];
            /** Transport Conversions */
            transport_conversions: {
                [key: string]: unknown;
            }[];
            /** Validated Objects */
            validated_objects: {
                [key: string]: unknown;
            }[];
        };
        /** LogoutView */
        LogoutView: {
            /** End Session Url */
            end_session_url: string | null;
        };
        /** PendingProposal */
        PendingProposal: {
            /** Candidates */
            candidates: components["schemas"]["Entity"][];
            proposal: components["schemas"]["Entity"];
            /** Review Payload Key */
            review_payload_key: string;
        };
        /**
         * PendingProposals
         * @description Newest first. A decision must carry the ``review_payload_key`` of the payload the reviewer saw.
         */
        PendingProposals: {
            /** Proposals */
            proposals: components["schemas"]["PendingProposal"][];
        };
        /** ProjectInspection */
        ProjectInspection: {
            /** Approval Error */
            approval_error?: string | null;
            /** Artifacts */
            artifacts: components["schemas"]["ArtifactInspection"][];
            manifest: components["schemas"]["ProjectManifest"];
            project: components["schemas"]["EntityRef"];
            receipt?: components["schemas"]["ReviewReceipt"] | null;
            /** Stale Dependencies */
            stale_dependencies: components["schemas"]["Finding"][];
        };
        /** ProjectManifest */
        ProjectManifest: {
            /** Artifacts */
            artifacts: components["schemas"]["ArtifactSelection"][];
            /** Authoring Context */
            authoring_context: string;
            design: components["schemas"]["EntityRef"];
            /**
             * Format
             * @default authoring-project
             * @constant
             */
            format: "authoring-project";
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            previous?: components["schemas"]["EntityRef"] | null;
            /** Project Id */
            project_id: string;
            /** Required Kinds */
            required_kinds: ("SOURCE" | "SYLLABUS" | "ASSESSMENT" | "TEACHER_CONTENT" | "TRAINER_CONTENT")[];
        };
        /** Provenance */
        Provenance: {
            /**
             * Origin
             * @enum {string}
             */
            origin: "CONFIGURATION" | "GENERATED_PROPOSAL" | "INITIAL_CONTEXT" | "HUMAN_DECISION" | "OBSERVED_EVENT" | "UNRESOLVED_GAP";
            /** Rationale */
            rationale?: string | null;
            /** Responsible */
            responsible: string;
            /** Sources */
            sources?: string[];
        };
        /** ReleasedArtifact */
        ReleasedArtifact: {
            receipt?: components["schemas"]["ReviewReceipt"] | null;
            resource: components["schemas"]["EntityRef"];
        };
        /** ReleaseInspection */
        ReleaseInspection: {
            /** Artifacts */
            artifacts: components["schemas"]["ReleasedArtifact"][];
            /** Closure */
            closure: components["schemas"]["EntityRef"][];
            /** Findings */
            findings: components["schemas"]["Finding"][];
            manifest: components["schemas"]["ReleaseManifest"];
            project_receipt?: components["schemas"]["ReviewReceipt"] | null;
            receipt?: components["schemas"]["ReviewReceipt"] | null;
            release: components["schemas"]["EntityRef"];
        };
        /** ReleaseManifest */
        ReleaseManifest: {
            /** Artifacts */
            artifacts: components["schemas"]["EntityRef"][];
            /** Authoring Context */
            authoring_context: string;
            design: components["schemas"]["EntityRef"];
            domain: components["schemas"]["EntityRef"];
            /**
             * Format
             * @default authoring-release
             * @constant
             */
            format: "authoring-release";
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            project: components["schemas"]["EntityRef"];
        };
        /** ReviewReceipt */
        ReviewReceipt: {
            change: components["schemas"]["EntityRef"];
            decision: components["schemas"]["EntityRef"];
            proposal: components["schemas"]["EntityRef"];
        };
        /** ScenarioInput */
        ScenarioInput: {
            /** Competency Ids */
            competency_ids: string[];
            /** Diagnostics */
            diagnostics: {
                [key: string]: unknown;
            }[];
            /** Excluded Scenario Object Ids */
            excluded_scenario_object_ids: string[];
            /** Limitations */
            limitations: string[];
            /** Objects */
            objects: components["schemas"]["SourceObject"][];
            /** Project Id */
            project_id: string;
            /**
             * Purpose
             * @default AUTHORING_REVIEW
             * @constant
             */
            purpose: "AUTHORING_REVIEW";
            /** Root Id */
            root_id: string;
            /** Scenario Model Id */
            scenario_model_id: string;
            /** Source Sha256 */
            source_sha256: string;
        };
        /** SelectedExcerpt */
        SelectedExcerpt: {
            /** Content Sha256 */
            content_sha256: string;
            /** Document Id */
            document_id: string;
            /** Limitations */
            limitations: string[];
            /** Purpose */
            purpose: string;
            /** Resource Id */
            resource_id: string;
            /** Resource Version */
            resource_version: string;
        };
        /** SessionView */
        SessionView: {
            /** Csrf Token */
            csrf_token: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /** Subject Key */
            subject_key: string;
        };
        /**
         * SourceObject
         * @description Transport envelope, not a generated AIM-PRO domain class.
         */
        SourceObject: {
            /** Attributes */
            attributes: {
                [key: string]: unknown;
            };
            /** Children */
            children: {
                [key: string]: string[];
            };
            /** Class Name */
            class_name: string;
            /** Id */
            id: string;
            /** Metamodel Id */
            metamodel_id: string;
            /** Model Id */
            model_id: string;
            /** Name */
            name?: string | null;
            /** Package */
            package: string;
            /** References */
            references: {
                [key: string]: string[];
            };
        };
        /** SourceQuery */
        SourceQuery: {
            /**
             * K
             * @default 20
             */
            k: number;
            /** Query */
            query: string;
        };
        /** SourceSelectionSummary */
        SourceSelectionSummary: {
            /**
             * Coverage Requirements
             * @default []
             */
            coverage_requirements: components["schemas"]["CoverageRequirement"][];
            /** Documents */
            documents: components["schemas"]["SelectedExcerpt"][];
            /** Queries */
            queries: components["schemas"]["SourceQuery"][];
            /** Trace Sha256 */
            trace_sha256: string;
        };
        /** SyllabusArtifact */
        SyllabusArtifact: {
            /** Context Id */
            context_id: string;
            /**
             * Curator
             * @default syllabus-designer
             * @constant
             */
            curator: "syllabus-designer";
            draft: components["schemas"]["SyllabusDraft"];
            /**
             * Format
             * @default aimpro-syllabus
             * @constant
             */
            format: "aimpro-syllabus";
            /**
             * Format Version
             * @default 1
             * @constant
             */
            format_version: 1;
            outline: components["schemas"]["EntityRef"];
            review: components["schemas"]["SyllabusVerdict"];
            source_snapshot: components["schemas"]["EntityRef"];
            /** Units */
            units: components["schemas"]["UnitLink"][];
        };
        /** SyllabusDraft */
        SyllabusDraft: {
            /**
             * Gaps
             * @default []
             */
            gaps: string[];
            /**
             * Kind
             * @default SYLLABUS_DRAFT
             * @constant
             */
            kind: "SYLLABUS_DRAFT";
            /** Metamodel Fingerprint */
            metamodel_fingerprint: string;
            /** Source Sha256 */
            source_sha256: string;
            /** Title */
            title: string;
            /** Units */
            units: components["schemas"]["SyllabusUnit"][];
        };
        /** SyllabusUnit */
        SyllabusUnit: {
            /** Corpus Citations */
            corpus_citations: components["schemas"]["CorpusCitation"][];
            /**
             * Coverage
             * @default []
             */
            coverage: components["schemas"]["UnitCoverage"][];
            /** Key */
            key: string;
            /** Planned Intents */
            planned_intents: ("EXPLAIN" | "PRACTICE" | "ASSESS")[];
            /** Purpose */
            purpose: string;
            /** Source Competency Ids */
            source_competency_ids: string[];
            /** Source Practice Ids */
            source_practice_ids: string[];
            /** Source Target Id */
            source_target_id: string;
            /** Title */
            title: string;
        };
        /** SyllabusVerdict */
        SyllabusVerdict: {
            /** Citation Support */
            citation_support: boolean;
            /** Reason */
            reason: string;
            /** Source Alignment */
            source_alignment: boolean;
            /**
             * Verdict
             * @enum {string}
             */
            verdict: "ACCEPT" | "REJECT" | "UNCERTAIN";
        };
        /** UnitCoverage */
        UnitCoverage: {
            /** Planned Action */
            planned_action: string;
            /** Requirement Key */
            requirement_key: string;
        };
        /** UnitLink */
        UnitLink: {
            /** Key */
            key: string;
            node: components["schemas"]["EntityRef"];
        };
        /** ValidationIssue */
        ValidationIssue: {
            /** Loc */
            loc: (string | number)[];
            /** Msg */
            msg: string;
            /** Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    callback_auth_callback_get: {
        parameters: {
            query?: {
                code?: string | null;
                error?: string | null;
                state?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            303: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Identity provider unavailable */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    login_auth_login_get: {
        parameters: {
            query?: {
                /** @description Local path to return to */
                return_to?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            302: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Identity provider unavailable */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    logout_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LogoutView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    session_auth_session_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionView"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    context_summary_contexts__context_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ContextSummary"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    apply_contexts__context_id__applications_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApplicationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Entity"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    decide_contexts__context_id__decisions_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DecisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Entity"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    pending_proposals_contexts__context_id__pending_proposals_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PendingProposals"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    project_inspection_contexts__context_id__projects__project_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                project_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectInspection"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    project_syllabus_contexts__context_id__resources__resource_id__versions__version__project_syllabus_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                resource_id: string;
                version: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApprovedSyllabus"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    release_inspection_contexts__context_id__resources__resource_id__versions__version__release_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                context_id: string;
                resource_id: string;
                version: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReleaseInspection"];
                };
            };
            /** @description No valid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not authorized, unmapped identity or missing CSRF token */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Not found, or the context is unavailable */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Conflict with the current state; reload and retry */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Invalid request or data */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthView"];
                };
            };
            /** @description Internal error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorBody"];
                };
            };
        };
    };
}
