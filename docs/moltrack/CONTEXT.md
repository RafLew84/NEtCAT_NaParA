# MolTrack

MolTrack is the planned application context for analysing molecular fields in STM image series, especially molecule detections, molecular shapes, tracks, terrace/step occupancy, and ordering dynamics.

## Language

**MolTrack**:
A separate application context for molecular tracking and molecular-field analysis in STM image series.
_Avoid_: NanoTrack mode, NanoTrack panel

**NanoTrack**:
The existing application context for nanoparticle tracking, edge tracking, registration, and related STM sequence workflows.
_Avoid_: MolTrack

**Molecular Detection**:
A molecule observation marked on one working frame.
_Avoid_: Track seed, candidate status, YOLO box as source of truth

**Detection Editing**:
Direct editing of a **Molecular Detection** in the **MolTrack Workspace**.
_Avoid_: Formal correction step, review status

**Manual Detection Marking**:
User-created **Molecular Detection** marking on the active working frame.
_Avoid_: Detection propagation, manual track creation

**Detection Identity**:
The stable session identity of one **Molecular Detection** on one **Working Frame Index**.
_Avoid_: Molecular Track identity, cross-frame molecule identity

**Observed Frame Footprint**:
The pixels actually present for one frame in the coordinate view being used.
_Avoid_: Registered field of view as observed image

**Molecular Instance Mask**:
A shape mask assigned to one **Molecular Detection** on one frame.
_Avoid_: Tracking mask as measurement

**Local Instance Mask**:
A **Molecular Instance Mask** stored relative to its detection footprint rather than as a full-frame mask.
_Avoid_: Full-frame molecule mask

**Segmentation Prompt**:
A bbox, point, or mask input derived from a **Molecular Detection** to request an instance mask from a segmentation backend.
_Avoid_: Seed

**Segmentation Retry**:
A repeated segmentation attempt for the same **Molecular Detection** using a new **Segmentation Prompt** or **Segmentation Settings**.
_Avoid_: New detection

**Frame Segmentation**:
Segmentation that produces masks for detections on one frame without assuming identity over time.
_Avoid_: Tracking

**Temporal Mask Propagation**:
Segmentation propagation across frames using temporal model state.
_Avoid_: Guaranteed tracking

**Segmentation Backend**:
A model or method that produces **Molecular Instance Masks** from **Segmentation Prompts**.
_Avoid_: Detector

**Segmentation Settings**:
User-visible settings that influence how candidate **Molecular Instance Masks** are produced from **Segmentation Prompts**.
_Avoid_: Detector settings

**Mask Provenance**:
The segmentation backend and settings used to produce one **Molecular Instance Mask**.
_Avoid_: Detection source

**Molecular Track**:
A time-linked sequence of **Molecular Detections** believed to represent the same observed molecule.
_Avoid_: Guaranteed molecule identity, MVP requirement

**Identity Ambiguity**:
A condition where frame-to-frame changes are too large or molecule appearances are too similar to assign a reliable **Molecular Track**.
_Avoid_: Tracker failure as the only explanation

**Molecular Population Analysis**:
Frame-level analysis of molecule counts, density, coverage, shape statistics, and ordering without requiring persistent molecule identity.
_Avoid_: Tracking-first analysis

**Detection-First Molecular Analysis**:
Molecular analysis based on marked **Molecular Detections** and detection-footprint metrics before requiring masks or tracks.
_Avoid_: Mask-first MVP, tracking-first MVP

**Detection Footprint Metrics**:
Position and size measurements derived from a detection footprint such as a bbox.
_Avoid_: BBox coverage, molecular area

**Detection Footprint Size**:
The width, height, or footprint area of a **Molecular Detection** bbox expressed as detector footprint size.
_Avoid_: Molecular size, Molecular Area

**Mask Coverage**:
Coverage measured from selected **Molecular Instance Masks**.
_Avoid_: BBox coverage, footprint coverage

**Measurement Geometry**:
The geometry used to compute a molecule metric, either a detection footprint for position and size or a selected instance mask for shape and coverage.
_Avoid_: Mode, source, backend result

**Analysis Measurement Geometry**:
The measurement geometry selected for one analysis run or export.
_Avoid_: Mixed implicit geometry

**Molecular Area**:
An area measurement computed from a selected molecule shape boundary, not from an unconstrained detection bbox.
_Avoid_: BBox area, footprint area

**Molecular Position**:
The default XY point of a **Molecular Detection**, computed from the active **Measurement Geometry**.
_Avoid_: Raw bbox point, intensity peak

**Source Image Calibration**:
The physical scale that maps image pixels to nanometers for a **Source Image Series**.
_Avoid_: Display zoom, detector input size

**Series Calibration**:
A single **Source Image Calibration** shared by every frame in a **Working Image Series**.
_Avoid_: Per-frame scale in one analysis series

**Physical Coordinates**:
Coordinates expressed in nanometers using **Source Image Calibration**.
_Avoid_: Pixel coordinates as reported measurement

**Series Physical Coordinates**:
Local **Physical Coordinates** anchored to the analysed image series rather than to absolute instrument offsets.
_Avoid_: Instrument-offset coordinates as default analysis coordinates

**NanoTrack Coordinate Orientation**:
The image-oriented coordinate convention reused from **NanoTrack** for local series analysis.
_Avoid_: Separate MolTrack axis convention, instrument-axis convention

**Pixel Coordinates**:
Coordinates expressed in image pixels.
_Avoid_: Physical measurement coordinates

**Physical Molecular Metrics**:
Molecular positions, sizes, distances, densities, and region areas reported in nanometer-based units.
_Avoid_: Pixel-only metrics

**Molecular Density**:
The number of participating **Molecular Detections** divided by observed analysis area.
_Avoid_: Count divided by nominal unobserved region area

**Molecular Row Order**:
The degree to which marked molecular detections form row-like spatial arrangements within an **Analysis Region**.
_Avoid_: Visual impression only

**Row Order Analysis Settings**:
User-visible tolerances that define how imperfect molecular rows are recognised during row-order analysis.
_Avoid_: Hidden thresholds, fixed row rules

**Row Orientation**:
The dominant direction of row-like molecular arrangement in an **Analysis Region**.
_Avoid_: Scan direction

**Row Spacing**:
The estimated distance between neighbouring molecular rows in an **Analysis Region**.
_Avoid_: Nearest-neighbour distance

**Sixfold Bond-Orientational Order**:
The local or regional coherence of molecular-neighbour bond directions under sixfold rotational symmetry.
_Avoid_: Molecular Row Order, translational order, complete phase classification

**M6 Orientation Analysis Settings**:
The immutable, serializable settings that define first-shell neighbours, local sixfold order, orientation-domain construction, pair-correlation support, and related quality thresholds.
_Avoid_: Row Order Analysis Settings, hidden M6 thresholds

**First-Shell Coordination Graph**:
A sparse graph whose nodes are participating molecular positions and whose edges represent accepted first-shell neighbour relations.
_Avoid_: Molecular Track graph, all-pairs distance matrix

**M6 Orientation Domain**:
A spatially connected set of molecules with compatible sixfold bond orientation, where orientation is equivalent modulo 60 degrees.
_Avoid_: Molecular Row, translational domain, track cluster

**M6-Gated A/B/C Classification**:
An optional orientation classification that assigns A, B, C, or an unresolved state only to molecules belonging to an **M6 Orientation Domain**.
_Avoid_: Independent whole-frame A/B/C classification, Texture Domain detection

**Orientation Subdomain**:
The set of molecules assigned one uppercase orientation-class label within one full **M6 Orientation Domain**. Each label denotes at most one subdomain per M6 domain, retains the same meaning across domains, and may contain spatially disconnected groups; automatic classification supplies A, B, or C, while labels D through Z are user-created.
_Avoid_: Connected component, whole-domain orientation label, M6 Orientation Domain

**Orientation Class Catalog**:
The working-series-wide ordered set of orientation labels A through Z whose meanings remain consistent across all frames and **M6 Orientation Domains**. A, B, and C are predefined for automatic classification; additional labels are introduced manually in alphabetical order. A manual label may be removed only after it has no molecule assignments; recreating that empty label reuses the letter without creating a distinct generation.
_Avoid_: Per-domain label namespace, frame-local class meaning

**Manual Orientation Decision**:
A user-authored, frame-local assignment of an A-Z class or an explicit unresolvable state to one **Molecular Detection**, independent of its M6 membership and without algorithmic confidence. It may replace an automatic A/B/C result in the effective view while preserving that automatic result for audit and reset.
_Avoid_: Classifier confidence, destructive A/B/C edit, M6 membership

**Effective Orientation Class**:
The A-Z class presented after applying a **Manual Orientation Decision** to the preserved automatic result. It contributes to an **Orientation Subdomain** only while the molecule belongs to an effective full **M6 Orientation Domain**.
_Avoid_: Automatic classifier label, whole-domain orientation label

**Effective Orientation Composition**:
The complete distribution of **Effective Orientation Classes** and unresolved molecules within one effective full **M6 Orientation Domain**. It is the domain-level orientation result rather than a single A-Z, Mixed, or Unknown label.
_Avoid_: Effective domain label, classifier evidence summary

**Unresolvable Orientation**:
An explicit reviewer decision that no A-Z class can be assigned to a molecule. It is distinct from an unreviewed molecule, an automatic classifier abstention, and a molecule that was not eligible for automatic classification.
_Avoid_: Unknown orientation class, missing annotation, not gated

**Stale Automatic Orientation Result**:
A preserved automatic orientation result whose M6 gate no longer matches the effective M6 membership. It remains audit evidence but cannot supply an **Effective Orientation Class** until orientation classification is rerun against the effective gate.
_Avoid_: Compatible automatic fallback, discarded classifier result

**Molecule Diagnostic Funnel**:
The ordered, per-molecule account from source input and geometry through domain and orientation evidence to the automatic, manual, and effective results. It preserves each stage and its cause even when a capability is unavailable, a gate prevents execution, or a later decision rejects earlier evidence.
_Avoid_: Final-label explanation, backend log, reconstructed UI trace

**Diagnostic Stage Result**:
One stage of a **Molecule Diagnostic Funnel**, recording execution availability separately from its scientific or post-processing decision, together with typed evidence and provenance. Earlier raw evidence remains part of the result after a threshold rejection, component filter, or manual correction.
_Avoid_: Single overloaded status, mutable pipeline state, discarded raw prediction

**Diagnostic Reason Code**:
A controlled explanation of why a **Diagnostic Stage Result** was accepted, not run, unavailable, rejected, ambiguous, filtered, or manually overridden. It distinguishes missing data, threshold rejection, insufficient evidence, conflict, post-processing, and manual action without pretending backend-native reasons are equivalent.
_Avoid_: Free-text-only reason, missing value encoded as zero, backend reason flattening

**Manual Membership Correction**:
A user-authored, frame-local override of automatic molecule membership in an **M6 Orientation Domain** or **Orientation Subdomain**. It preserves the automatic result and may be removed to restore automatic membership.
_Avoid_: Destructive result edit, classifier retraining label

**Manual M6 Orientation Domain**:
A frame-local **M6 Orientation Domain** created by the user from selected molecules in the effective result. It retains one stable identity across composition changes, reversible removal, and restoration without mutating the preserved automatic domain result.
_Avoid_: Edited automatic snapshot, persistent cross-frame domain

**Domain Correction Set**:
The frame-local collection of manual domain and orientation decisions whose current immutable revision is anchored to one automatic result, source geometry, annotation version, and series **Orientation Class Catalog**. It preserves correction history and stable manual-domain identities across explicit rebases without owning a copy of the automatic or effective result.
_Avoid_: Edited automatic snapshot, duplicated effective result, cross-frame correction set

**Domain Correction Apply**:
The explicit acceptance of one prepared, frame-local domain or orientation change for a frozen set of **Detection Identities**. One apply is one all-or-nothing history atom regardless of whether its selection came from a point, multiple points, or polygons.
_Avoid_: Per-molecule partial commit, selection gesture, persistent polygon region

**Domain Correction History**:
The frame-local, auditable sequence of accepted correction and review decisions sharing one automatic-result anchor. Each decision yields a new immutable **Domain Correction Set** value; history supports whole-atom undo and redo without erasing earlier decisions and never crosses a **Correction Rebase** into a differently anchored revision.
_Avoid_: Transient view undo stack, destructive event deletion, cross-revision undo

**Domain Correction Conflict**:
A condition discovered while preparing a **Domain Correction Apply** that either blocks the whole change, requires explicit acknowledgement, or informs the operator without preventing the change. A deliberate difference from the preserved automatic result alone is not a blocking conflict.
_Avoid_: Partial apply, silent membership transfer, every automatic override as an error

**Correction Rebase**:
An explicit, audited transfer of portable manual decisions from one immutable **Domain Correction Set** revision to a successor anchored to a new automatic result for the same physical frame. It preserves manual-domain identities but never transfers acceptance of the previous automatic result.
_Avoid_: Silent rerun overwrite, automatic domain-ID matching, destructive correction migration

**Stale Domain Correction**:
A preserved **Domain Correction Set** revision that cannot be applied to the active source and automatic result because its identity, geometry, or molecule mapping is incompatible or unresolved. It remains audit evidence but cannot contribute to an **Effective Domain Projection** or reviewed reference data.
_Avoid_: Superseded correction revision, review workflow status, deleted correction history

**Effective Domain Projection**:
The current domains, molecule memberships, orientation subdomains, review dispositions, and recalculated metrics derived from one preserved automatic result plus its **Domain Correction Set**. It is a reproducible view rather than a second mutable source of truth.
_Avoid_: Stored corrected snapshot, destructive automatic result edit

**Domain Correction Workspace**:
The correction-aware state for one working series: preserved automatic results, the series orientation catalog, frame-local correction histories, review and rebase records, and molecule diagnostic funnels. It excludes runtime capability catalogs and treats the effective projection as derived.
_Avoid_: Corrected automatic snapshot, manual differences only, runtime classifier registry

**Effective Projection Checkpoint**:
A fingerprinted materialization of an **Effective Domain Projection** retained solely to verify reproducibility across Save, Open, and export. A mismatch quarantines the related corrections instead of making the checkpoint a source of truth.
_Avoid_: Mutable effective result, authoritative corrected snapshot, trusted cache without validation

**Correction-Aware Analysis Package**:
A versioned export of the preserved automatic result, current effective per-molecule state, correction and rebase audit, review, recalculated metrics, orientation catalog, and diagnostic funnels for a complete frozen scope. It includes accepted automatic cases and reports target-specific readiness rather than representing manual differences alone.
_Avoid_: Corrections-only export, automatic-only analysis package, reviewed flag without complete scope

**Effective Domain Membership**:
The membership presented and exported after applying **Manual Membership Corrections** to the preserved automatic result.
_Avoid_: Automatic membership, overwritten classifier result

**M6 Reference Dataset**:
A versioned, target-specific collection of independent **Reference Measurement Groups** whose frame-local effective M6 memberships have complete reference review and immutable source provenance. It is partitioned into M6 parameter calibration and independent M6 preset validation and contains no orientation-class tuning target.
_Avoid_: Live analysis state, single-file tuning snapshot, orientation-class training labels

**Orientation Reference Dataset**:
A versioned, target-specific collection of independent **Reference Measurement Groups** whose effective **Orientation Subdomain** memberships have complete reference review. It preserves raw images, segmentation geometry, physical calibration, scan angle, sample coordinates, and source provenance required to calibrate and validate orientation independently of M6.
_Avoid_: M6 domain calibration target, combined M6-orientation tuning dataset

**Reference Measurement Group**:
The indivisible split unit containing frames from one independent physical measurement or acquisition. Renames, copies, conversions, derived files, molecules, and adjacent frames from that measurement do not create independent units.
_Avoid_: File path, individual frame, random molecule split

**Reference Source Revision**:
An immutable, content-identified revision of source bytes and their acquisition lineage used by a reference dataset. Different bytes are a new revision even at the same path; the same verified bytes may be relocated without becoming a new revision.
_Avoid_: Mutable source path, silently replaced source file

**Reference Dataset Version**:
An immutable snapshot of one target-specific reference dataset, including its Calibration and Validation partition identities and parent version. Updating a dataset creates a successor and preserves every earlier version.
_Avoid_: Mutable dataset file, in-place reference update

**Reference Validation Epoch**:
A comparison lineage in which the Validation partition identity of a reference dataset remains frozen. Any accepted Validation membership or source-revision change starts a new epoch rather than extending the old comparison line.
_Avoid_: Editable holdout, silent validation refresh

**M6 Calibration Campaign**:
A controlled comparison of M6 backend candidates using one immutable **M6 Reference Dataset** version, one **First-Shell Geometry Policy**, one **M6 Selection Objective**, and one **Reference Validation Epoch**. Calibration selects a frozen shortlist before Validation is revealed.
_Avoid_: Repeated holdout tuning, automatic preset activation

**First-Shell Geometry Policy**:
A fingerprinted rule that constructs first-shell neighbours either from a fixed physical-distance range or a deterministic adaptive estimate with an explicit fixed fallback. It is selected as a geometry experiment before M6 classification parameters are calibrated.
_Avoid_: Hidden sweep parameter, unversioned radius guess

**M6 Preset**:
A named, saved configuration that combines one domain backend, complete **M6 Orientation Analysis Settings**, and one **First-Shell Geometry Policy** for reuse in later analyses. It is a runnable configuration, not evidence of calibration, validation, or approval.
_Avoid_: Calibration report, approved candidate, immutable preset revision

**M6 Preset Library**:
The user's collection of saved **M6 Presets** together with exactly one active selection used as the default for future analyses.
_Avoid_: Per-session preset list, validation registry, preset profile hierarchy

**M6 Preset Working Copy**:
The editable configuration prepared from a new or saved **M6 Preset** for experimentation, analysis, and an explicit Save or Save As decision. It does not change the saved preset merely because its values are edited or executed.
_Avoid_: Automatic preset update, preset revision history, live mutation of a saved preset

**Active M6 Preset**:
The single saved **M6 Preset** selected in the **M6 Preset Library** to initialize future M6 analyses by default. It is not the configuration of an already running or completed analysis.
_Avoid_: Current analysis result, automatic recompute trigger, project preset profile

**Built-In M6 Preset**:
A shipped, read-only **M6 Preset** that can be activated directly or copied into an editable user preset.
_Avoid_: Locked user preset, automatically approved preset, mutable product default

**M6 Selection Objective**:
The predeclared constrained rule that rejects candidates below minimum membership precision or local stability, then prefers high recall while applying separate normalized split and merge penalties. Its thresholds and penalty weights belong to the campaign record rather than to implicit product defaults.
_Avoid_: ARI-only ranking, unconstrained weighted score, post-Validation threshold change

**M6 Candidate Shortlist**:
The immutable selection of exactly one Calibration-qualified candidate per compared M6 backend, together with the objective and tie-break rule that selected it. It is frozen before Validation access.
_Avoid_: Ranked Validation variants, editable post-holdout selection

**Validation Access Receipt**:
The immutable evidence that one **M6 Candidate Shortlist** was evaluated against one frozen Validation partition, including the dataset, epoch, geometry, objective, shortlist, and access fingerprints. A receipt closes that epoch to further candidate tuning or repeated Validation access.
_Avoid_: Reusable holdout permission, mutable validation log

**Reference Review Status**:
The target-specific workflow state that says whether one source frame is still a draft or has passed complete M6-reference or orientation-reference review. A relevant annotation, source, or scope change returns a reviewed frame to draft; this is not a status of the underlying **Molecular Detections**.
_Avoid_: Detection review status, shared M6-and-orientation review flag

**Reference Review Scope**:
The frozen set of molecule identities that must receive an explicit scientific and review decision before one frame can be complete for a specific reference target, together with explicit reasons for any ineligible exclusions.
_Avoid_: Manually changed molecules only, current mutable selection

**Review Abstention**:
An explicit, reasoned decision that an eligible molecule is uncertain for M6 membership or unresolvable for orientation. It completes review of that molecule without pretending that a resolved scientific label exists.
_Avoid_: Missing review, forced label, silent exclusion

**Reference Review Disposition**:
The explicit relationship between one reviewed molecule's effective scientific state and its preserved automatic result: accepted automatic, corrected, created, or rejected. Automatic abstention cannot be accepted as human review, and the disposition remains independent of both scientific state and frame workflow.
_Avoid_: Scientific class, domain membership, frame workflow state

**Reference Review Sign-Off**:
The explicit, timestamped single-operator decision that one frame's current **Reference Review Scope** is complete for one reference target. It is valid only while the signed source, scope, and annotations remain unchanged.
_Avoid_: Automatic completion, save operation, reviewer identity

**Reference Dataset Readiness**:
The derived eligibility of one dataset version for calibration or validation after every included frame has a valid target-specific **Reference Review Sign-Off** and current provenance. A saved draft dataset is not ready.
_Avoid_: Editable reviewed flag, partially reviewed training data

**Domain Analysis**:
The streamlined range workflow that always finds **M6 Orientation Domains** and may then run an optional gated classifier such as **M6-Gated A/B/C Classification**.
_Avoid_: Position Analysis, independent Texture Domains workflow

**Spatial Command Center**:
The selected Domain Analysis UI architecture in which the image canvas remains the central working surface, a vertical rail selects the workflow stage, and one contextual bottom sheet exposes the current tools and data. Every stage projects one shared **Domain Correction Workspace** through one controller; widgets do not own parallel scientific state.
_Avoid_: Separate correction wizard, independent stage controllers, HTML prototype as production UI

**Domain Analysis Documentation Set**:
The versioned user guide, technical reference, format reference, migration/troubleshooting guide, screenshots, and verified clean-session walkthrough shipped with the correction-aware **Domain Analysis** workflow. Its compatibility declarations and Help link are release-gated behavior rather than optional follow-up prose.
The MolTrack 0.1.0 release snapshot is session v3, Domain Analysis state v2, correction-aware export v10, M6/Orientation Reference Dataset target schema v2 with envelope v2, M6 preset/library v1, and campaign report v2.
_Avoid_: Prototype notes as user documentation, unversioned screenshots, documentation after release

**Molecular Detector**:
A model or method that proposes **Molecular Detections** on each frame.
_Avoid_: Measurement source of truth

**Detector Run Settings**:
User-selected settings for one execution of a **Molecular Detector**.
_Avoid_: Detection provenance, Molecular Detection state

**Detector Frame Scope**:
The frame set on which a detector run is executed.
_Avoid_: Detection Search Scope

**Similarity-Based Molecular Detector**:
A molecular detector that uses one or more example molecules as prompts to propose similar **Molecular Detections** in an image region.
_Avoid_: Segmentation-only backend

**Concept-Based Molecular Detector**:
A molecular detector that uses a molecule concept prompt to propose all matching **Molecular Detections** in an image region.
_Avoid_: Single-object segmenter

**Molecule Concept Prompt**:
A text, image-exemplar, or point-based prompt describing the molecular concept to find.
_Avoid_: Track seed, single-object prompt

**Concept Prompt Point**:
A positive or negative point selected on the active frame to guide a **Molecule Concept Prompt**.
_Avoid_: Molecular Detection, measurement point

**Single-Frame Concept Detection**:
A concept-based detection workflow that proposes **Molecular Detections** on one working frame from **Molecule Concept Prompts**.
_Avoid_: Tracking, temporal propagation, sequence detection

**Detection Search Scope**:
The image area searched by a molecular detector for new **Molecular Detections**.
_Avoid_: Measurement region

**Whole-Frame Detection Search Scope**:
A **Detection Search Scope** covering the frame's **Observed Frame Footprint**.
_Avoid_: Registered Field of View search

**Detection Insertion Policy**:
The rule used when detector proposals are added to existing **Molecular Detections** in a **Detection Search Scope**.
_Avoid_: Review status, detector-specific overwrite

**Detection Match Rule**:
The criteria used to decide whether a detector proposal represents the same molecule as an existing **Molecular Detection**.
_Avoid_: Exact duplicate by source, automatic identity proof

**Analysis Region**:
A named image area used as a separate measurement domain.
_Avoid_: Unnamed ROI

**Region Role**:
An optional domain label for an **Analysis Region**, such as terrace or step edge.
_Avoid_: Required region type

**Region Editing Tool**:
The active workspace tool used to create and edit **Analysis Regions**.
_Avoid_: Separate workflow stage

**Region Identity**:
The stable identity of an **Analysis Region** across frames, even when its geometry is copied or edited.
_Avoid_: Geometry as identity

**Default Analysis Region**:
The whole observed frame used as one untyped **Analysis Region** when the user has not defined any regions.
_Avoid_: Hidden region, terrace by default

**Copied Analysis Region**:
An **Analysis Region** reused on later frames with the same coordinates.
_Avoid_: Per-frame region by default

**Region Coordinate Scope**:
The coordinate scope that anchors an **Analysis Region**, either native frame coordinates or registered coordinates.
_Avoid_: ROI mode, view mode

**Registered Analysis Region**:
An **Analysis Region** anchored to **Registered Coordinates** so it represents the same surface area across shifted frames.
_Avoid_: Expanded-canvas ROI, warped ROI

**Registered Field of View**:
The spatial extent covered by the **Working Image Series** after applying **Registration Shifts** in a shared coordinate system.
_Avoid_: Expanded canvas, padded image

**Observed Region Footprint**:
The part of an **Analysis Region** that overlaps pixels actually present on one working frame.
_Avoid_: Region area when unobserved pixels are included

**Regional Detection Membership**:
The assignment of a **Molecular Detection** to an **Analysis Region** by testing its **Molecular Position** against the frame's **Observed Region Footprint**.
_Avoid_: BBox overlap membership, mask-area membership

**Terrace Region**:
An **Analysis Region** representing one molecular terrace or molecular field separated by a step.
_Avoid_: Step, level, field when used ambiguously

**Step Edge Region**:
An **Analysis Region** representing the band around a step edge.
_Avoid_: Terrace

**Registration Shift**:
A per-frame global XY translation used to align frames into a shared coordinate system.
_Avoid_: Local warp, morphology-changing optical flow

**Optical-Flow Translation Registration**:
Use of optical-flow-derived evidence to estimate a global **Registration Shift**.
_Avoid_: Optical-flow warp, local deformation

**Registration Settings**:
User-visible settings used to compute **Registration Shifts** for a **Working Image Series**.
_Avoid_: Local warp settings

**Native Frame Coordinates**:
The original per-frame coordinate system before applying a **Registration Shift**.
_Avoid_: Raw frame when coordinate system is meant

**Registered Coordinates**:
The shared coordinate system after applying **Registration Shifts**.
_Avoid_: Warped image coordinates

**Analysis Coordinate Context**:
The coordinate context used to compute spatial metrics and plots for an analysis run.
_Avoid_: Stored coordinate system

**MolTrack Session**:
A saved and loadable molecular-field analysis state for exactly one source image series.
_Avoid_: Project container, multi-series project, export file

**MolTrack Session File**:
A saved file that stores one **MolTrack Session** for later continuation of work.
_Avoid_: Source Image Series, Analysis Export, project container

**Session Save Command**:
A user-triggered command that writes the current **MolTrack Session** to a **MolTrack Session File**.
_Avoid_: Autosave as MVP default

**Unsaved Session Changes**:
Changes to a **MolTrack Session** that have not yet been written by a **Session Save Command**.
_Avoid_: Exported state

**Transient Workspace View State**:
Temporary UI navigation state such as active frame, zoom, or pan.
_Avoid_: Analysis state, session dirty state

**Source Series Reference**:
The saved reference from a **MolTrack Session File** to the source STM file or files.
_Avoid_: Bundled source image data

**Source Series Fingerprint**:
A lightweight identity check for the source STM file or files referenced by a **MolTrack Session File**.
_Avoid_: Full source image copy, full-file hash as default

**Lightweight Source Fingerprint**:
A fast **Source Series Fingerprint** based on source file metadata and STM series metadata.
_Avoid_: Cryptographic source identity

**Source Image Series**:
The original STM image series being analysed.
_Avoid_: Session file

**Supported STM Source Format**:
One of the STM source formats accepted by **MolTrack**: MPP, STP, or S94.
_Avoid_: Generic image format

**Source Import Validation**:
Validation that source STM files can form one physically calibrated **Working Image Series**.
_Avoid_: Best-effort import with inconsistent scale

**Working Image Series**:
The frame series after import-time ordering and frame removals.
_Avoid_: Source Image Series when removed frames matter

**Source File Name Ordering**:
Natural ordering of multiple source image files by file name before they become a **Working Image Series**.
_Avoid_: Lexicographic ordering, manual frame ordering as default

**Source Movie Frame Ordering**:
The internal frame order of a single source movie file before it becomes a **Working Image Series**.
_Avoid_: File-name ordering for one movie

**Removed Frame**:
A frame removed from the **Working Image Series** and unavailable to downstream analysis.
_Avoid_: Excluded frame, hidden frame

**Working Frame Index**:
The frame index inside the **Working Image Series** after ordering and removals.
_Avoid_: Source index

**Source Frame Index**:
The original frame index in the **Source Image Series** before removals.
_Avoid_: Working index

**Frame-Index Time Axis**:
The use of **Working Frame Index** as the default progression axis for molecular-field changes.
_Avoid_: Physical time as required axis

**Derived Analysis Data**:
Analysis state produced from a **Source Image Series**, such as detections, regions, shifts, masks, links, and metrics.
_Avoid_: Source data

**Analysis Metric Cache**:
Cached metric values derived from session state.
_Avoid_: Session source of truth

**Analysis Settings**:
Saved settings that define how metrics and spatial analysis are computed from a **MolTrack Session**.
_Avoid_: Detector Run Settings, metric cache

**Analysis Export**:
An output file generated from a **MolTrack Session** for reporting, plotting, or model training.
_Avoid_: Session state

**Detection Metrics Export**:
An **Analysis Export** that reports one row per **Molecular Detection** on one **Working Frame Index**.
_Avoid_: Region summary export

**BBox Detection Metrics Export**:
A bbox-footprint **Detection Metrics Export** for detection-first analysis.
_Avoid_: Mask-shape export, coverage export

**Region Metrics Export**:
An **Analysis Export** that reports aggregated molecular-field metrics for one **Analysis Region** on one **Working Frame Index**.
_Avoid_: Per-detection export

**BBox Region Metrics Export**:
A bbox-footprint **Region Metrics Export** for detection-first analysis.
_Avoid_: Mask coverage export

**Auxiliary Pixel Export Columns**:
Pixel-coordinate columns included in an **Analysis Export** to support detector debugging and geometry inspection.
_Avoid_: Primary pixel metrics

**MolTrack Workspace**:
The interactive analysis surface where a user inspects frames, regions, detections, masks, and metrics for one **MolTrack Session**.
_Avoid_: Wizard

**STM Image View**:
The main workspace view showing the active STM frame with overlays.
_Avoid_: Export preview

**Frame Series Panel**:
The workspace panel for navigating the **Working Image Series**.
_Avoid_: Timeline as physical time

**Region Panel**:
The workspace panel for listing and managing **Analysis Regions**.
_Avoid_: Detector scope only

**Detection Panel**:
The workspace panel for listing, editing, and running molecular detection workflows.
_Avoid_: Detection review queue

**Analysis Export Panel**:
The workspace panel for analysis settings, metric recalculation, and exports.
_Avoid_: Session save command

**MolTrack Workspace Visualization**:
An interactive visualization generated from the current **MolTrack Session** inside the **MolTrack Workspace**.
_Avoid_: Analysis Export, saved plot report

**Active-Frame XY Visualization**:
A **MolTrack Workspace Visualization** of molecular positions on the active **Working Frame Index**.
_Avoid_: Frame-range trend view

**Frame-Range XY Visualization**:
A **MolTrack Workspace Visualization** of molecular positions over a selected frame range.
_Avoid_: Single active-frame view

**Divisualisation-Like View**:
A planned **MolTrack Workspace Visualization** style inspired by the user-provided `bentaculum/divisualisation` reference.
_Avoid_: Analysis Export, copied external data model

## Relationships

- **MolTrack** is separate from **NanoTrack**.
- **MolTrack** may reuse capabilities from **NanoTrack** without sharing its domain model.
- A **Molecular Track** contains zero or more gaps and may end when **Identity Ambiguity** becomes too high.
- **Molecular Detection** is the primary observation; **Molecular Track** is an optional later interpretation over detections.
- A **Molecular Detection** must be inside the frame's **Observed Frame Footprint**.
- A **Molecular Detection** cannot be created in an unobserved part of the **Registered Field of View**.
- **Detection Editing** is always available for marked detections.
- **Detection Editing** can add, remove, move, or resize a detection without entering a formal correction workflow.
- Each **Molecular Detection** has one **Detection Identity**.
- **Detection Identity** identifies a marked detection on one frame and does not imply cross-frame molecular identity.
- **Molecular Instance Masks** and **Detection Metrics Export** rows reference **Detection Identity**.
- Removing a **Molecular Detection** removes its **Detection Identity** from active analysis and exports.
- Removing a **Molecular Detection** also removes its candidate **Molecular Instance Masks** from active analysis state.
- A **Molecular Instance Mask** belongs to exactly one **Molecular Detection**.
- A **Local Instance Mask** is the preferred stored form of a **Molecular Instance Mask**.
- A **Molecular Detection** can exist without a **Molecular Instance Mask**.
- A **Molecular Instance Mask** cannot exist without a parent **Molecular Detection**.
- A **Molecular Detection** may have multiple candidate **Molecular Instance Masks**, with at most one selected as the measurement mask for default analysis.
- **Segmentation Settings** include mask probability threshold when the backend exposes probability-like mask output.
- Each **Molecular Instance Mask** has **Mask Provenance**.
- **Mask Provenance** is retained for candidate masks even though **Molecular Detections** do not need source history.
- A **Segmentation Prompt** can be derived from a **Molecular Detection** without changing the detection into a track seed.
- A segmentation backend produces **Molecular Instance Masks** from **Segmentation Prompts**.
- A **Segmentation Retry** creates another candidate **Molecular Instance Mask** for the same **Molecular Detection**.
- **Frame Segmentation** is the default mask-generation mode for **MolTrack**.
- **Temporal Mask Propagation** is optional and does not by itself prove **Molecular Track** identity.
- A **Segmentation Backend** is interchangeable as long as it produces **Molecular Instance Masks** for **Molecular Detections**.
- **Molecular Population Analysis** is the primary MVP analysis style in **MolTrack**.
- **Detection-First Molecular Analysis** is the initial MolTrack workflow.
- **Detection-First Molecular Analysis** uses **Molecular Detections** and **Detection Footprint Metrics** without requiring **Molecular Instance Masks**.
- Mask-shape analysis remains an optional later measurement layer and does not block detection-first workflows.
- **Detection Footprint Metrics** are available from marked detections without masks.
- **Detection Footprint Size** is a bbox-footprint metric and is not **Molecular Area**.
- Bbox-based **Region Metrics Export** reports counts, density, footprint-size statistics, and row-order metrics, but not coverage or occupancy.
- **Mask Coverage** is available only where measurement masks exist.
- **Measurement Geometry** separates bbox-based metrics from mask-based metrics.
- **Analysis Measurement Geometry** is selected per analysis run or export.
- Bbox-based **Analysis Measurement Geometry** ignores **Molecular Instance Masks** completely.
- Mask-based **Analysis Measurement Geometry** ignores detections without a selected **Molecular Instance Mask**.
- In mask-based **Analysis Measurement Geometry**, counts and density include only detections with a selected **Molecular Instance Mask**.
- **Molecular Area** requires mask-based or refined-shape **Measurement Geometry**.
- **Molecular Position** is the bbox center for footprint geometry and the geometric centroid for mask-based geometry.
- **Molecular Position** is computed from the full active **Measurement Geometry**, not from intersections with **Analysis Regions**.
- A **Source Image Calibration** is derived from the **Source Image Series** metadata when physical scale metadata is available.
- A **Working Image Series** has one **Series Calibration**.
- **Series Calibration** must be consistent before **Physical Molecular Metrics** are reported.
- **Physical Coordinates** are the primary reporting coordinates for **MolTrack** metrics.
- **Series Physical Coordinates** are the default coordinate frame for regions, molecule positions, XY plots, registration views, and exports.
- **Series Physical Coordinates** use **NanoTrack Coordinate Orientation**.
- Instrument offsets from source metadata may be retained as metadata, but they are not the default coordinate origin for **MolTrack** analysis.
- **Pixel Coordinates** may be retained for detector geometry, UI editing, and auxiliary diagnostics, but they do not replace **Physical Molecular Metrics**.
- **Physical Molecular Metrics** use nanometers for positions and lengths, square nanometers for areas, and inverse square nanometers for densities.
- **Molecular Density** uses **Observed Region Footprint** area as the denominator.
- **Molecular Density** is unavailable when observed analysis area is zero.
- A **Molecular Instance Mask** may be used for workspace visualization even when it is not included in an **Analysis Export**.
- **Molecular Row Order**, **Row Orientation**, and **Row Spacing** can be estimated from marked **Molecular Detections**.
- **M6-Gated A/B/C Classification** requires a compatible **M6 Orientation Domain** result and never classifies molecules outside those domains.
- **Domain Analysis** produces **M6 Orientation Domains** before running any selected gated classifier on the same analysis range and coordinate context.
- **Spatial Command Center** renders one **Domain Correction Workspace** through one workspace controller; its canvas, hierarchy, ledger, diagnostics, and bottom sheet are projections of the same immutable snapshot.
- In **Spatial Command Center**, highlight is navigational and cannot change selection or create a **Domain Correction Apply**.
- The **Domain Analysis Documentation Set** is complete only when its Quick start is verified on a clean TTMAPP session, its screenshots come from production **Spatial Command Center**, and application Help opens the version-compatible user guide.
- One **Domain Correction Apply** freezes and deduplicates its **Detection Identities** and changes them as one all-or-nothing atom.
- Point and polygon selections prepare a **Domain Correction Apply** but do not become persistent domain regions.
- **Domain Correction History** survives session save and load within its current revision; a **Correction Rebase** makes the previous revision read-only history.
- Undoing a domain correction does not restore an earlier **Reference Review Sign-Off**; the affected target requires a new sign-off.
- One **Reference Measurement Group** belongs to at most one of Calibration or Validation within one **Reference Dataset Version**.
- A rename, copy, conversion, adjacent frame, or derived source from the same acquisition remains in the same **Reference Measurement Group** and cannot cross the split.
- **M6 Reference Dataset** and **Orientation Reference Dataset** partition measurements independently; the same group may occupy different splits for the two targets.
- A successor **Reference Dataset Version** in the same **Reference Validation Epoch** may change Calibration but must preserve the Validation partition identity.
- Changing Validation starts a new **Reference Validation Epoch**, and changing source bytes creates a new **Reference Source Revision**; neither operation overwrites earlier versions.
- **Reference Dataset Readiness** is invalidated by source drift or by a change to the signed target-specific review scope.
- One **M6 Calibration Campaign** selects its **First-Shell Geometry Policy** on Calibration before sweeping classification parameters.
- An **M6 Selection Objective** treats membership precision and local stability as eligibility constraints; recall and separate split/merge penalties rank only eligible candidates.
- One **M6 Candidate Shortlist** contains at most one candidate from each compared backend and uses the same reference version, split, geometry policy, and objective for every backend.
- Validation is revealed once per **Reference Validation Epoch** and creates a **Validation Access Receipt**; a negative result remains valid evidence and cannot authorize retuning against that epoch.
- A new candidate after Validation access requires a new **Reference Dataset Version** and **Reference Validation Epoch**, while the earlier campaign report and receipt remain immutable audit history.
- An **M6 Preset** may be created or activated without an **M6 Calibration Campaign** or **Validation Access Receipt**; those artifacts can inform a user choice but never gate or automate it.
- Editing or executing an **M6 Preset Working Copy** does not change a saved **M6 Preset** until an explicit Save or Save As decision.
- Exactly one saved, compatible preset is the **Active M6 Preset**, and changing it affects only the default starting point for future analyses.
- Every M6 analysis freezes the backend, settings, **First-Shell Geometry Policy**, algorithm version, and configuration fingerprint used for that run; later preset changes do not alter existing results.
- A **Built-In M6 Preset** cannot be overwritten or deleted, but it may be copied into an editable preset in the **M6 Preset Library**.
- An effective molecule belongs to at most one **M6 Orientation Domain**; a later confirmed membership correction atomically replaces its earlier effective membership.
- A manual **M6 Orientation Domain** with no remaining members is represented as a tombstone rather than an active empty domain.
- A **Domain Correction Conflict** never permits a partial commit: a blocked or outdated prepared change leaves the entire **Domain Correction Set** unchanged.
- **Molecular Row Order**, **Row Orientation**, and **Row Spacing** are reported per **Analysis Region** and **Working Frame Index**.
- Row-order trends are derived from **Region Metrics Export** across the **Frame-Index Time Axis**.
- **Molecular Row Order** is interpreted together with the **Row Order Analysis Settings** used to estimate it.
- **Row Order Analysis Settings** include minimum region population, neighbour scale, angular tolerance, row-width tolerance, and expected row-spacing range.
- If an **Analysis Region** has fewer detections than the minimum region population in **Row Order Analysis Settings**, row-order metrics are unavailable rather than zero.
- A **Molecular Detection** participates in analysis while it remains marked in the **MolTrack Workspace**.
- A **Molecular Detector** proposes **Molecular Detections**, which can be edited or removed before analysis.
- **Detector Run Settings** configure one detector execution and do not become source history for created **Molecular Detections**.
- **Detector Run Settings** are not saved as session state unless they are part of saved **Analysis Settings**.
- YOLO **Detector Run Settings** include checkpoint selection, confidence threshold, IoU/NMS threshold, **Detector Frame Scope**, **Detection Search Scope**, **Detection Insertion Policy**, and basic **Detection Match Rule** parameters.
- **Detector Frame Scope** may be the active frame, a frame range, or the whole **Working Image Series** when the detector supports batch operation.
- YOLO detection supports active-frame, frame-range, and whole-series **Detector Frame Scope**.
- SAM 3 **Single-Frame Concept Detection** uses **Detector Frame Scope**, but MVP support is active-frame only.
- SAM 3 **Detector Run Settings** include **Molecule Concept Prompt**, optional text prompt, positive and negative **Concept Prompt Points**, confidence or probability threshold, **Detection Search Scope**, **Detection Insertion Policy**, and basic **Detection Match Rule** parameters.
- Manual marking and automatic detection both create **Molecular Detections**.
- **Manual Detection Marking** creates detections on the active frame only.
- A **Similarity-Based Molecular Detector** may also produce candidate **Molecular Instance Masks** for the detections it proposes.
- A **Concept-Based Molecular Detector** is a **Similarity-Based Molecular Detector** when it uses molecule exemplars or concept prompts to find matching instances.
- A **Molecule Concept Prompt** may be built from an existing **Molecular Detection**, image exemplars, text, and positive or negative **Concept Prompt Points**.
- A **Concept Prompt Point** guides detection but does not itself participate in analysis.
- **Concept Prompt Points** are temporary detector-run inputs and are not saved as session analysis state.
- Image exemplars used in a **Molecule Concept Prompt** are temporary detector-run inputs and are not saved as session analysis state.
- **Single-Frame Concept Detection** creates detections only on the target working frame and does not imply tracking.
- **Single-Frame Concept Detection** runs on one **Working Frame Index** from a **Source Image Series** using a **Supported STM Source Format**.
- **Single-Frame Concept Detection** runs on the active frame, not as a batch detector over a frame range.
- **Detection Search Scope** may be an **Analysis Region**, the **Default Analysis Region**, or an explicit **Whole-Frame Detection Search Scope**.
- **Detection Search Scope** applies to all molecular detectors, including YOLO and similarity-based detectors.
- A detector run uses one **Detection Search Scope** at a time.
- When no user-defined **Analysis Regions** exist, detector UI uses **Whole-Frame Detection Search Scope** rather than presenting the **Default Analysis Region** as a visible region.
- **Whole-Frame Detection Search Scope** covers only the frame's **Observed Frame Footprint**.
- When a detector searches a registered **Analysis Region**, the effective search area is the region's **Observed Region Footprint** for that frame.
- A detector run uses a **Detection Insertion Policy** when proposed **Molecular Detections** overlap detections already marked in its **Detection Search Scope**.
- A **Detection Match Rule** determines whether a detector proposal overlaps an existing **Molecular Detection** strongly enough to be treated as the same marked molecule.
- **Detection Match Rule** parameters can include bbox overlap, centroid distance, and mask overlap when candidate masks exist.
- The default **Detection Insertion Policy** merges overlapping proposals with existing detections in the **Detection Search Scope**.
- Alternative **Detection Insertion Policies** may append all proposals or replace existing detections inside the **Detection Search Scope**.
- **Molecular Detections** are stored in working-frame coordinates, even when detected inside a crop or region.
- An **Analysis Region** defines the denominator for regional density and coverage.
- A **Default Analysis Region** is used only when no user-defined **Analysis Regions** exist.
- **Region Metrics Export** includes the **Default Analysis Region** only when no user-defined **Analysis Regions** exist.
- **Analysis Regions** are not required before detection; regional metrics can be recalculated after regions are added or edited.
- An **Analysis Region** may have no **Region Role**.
- **Terrace Region** and **Step Edge Region** are **Analysis Regions** with specific **Region Roles**.
- A **Region Editing Tool** creates and edits **Analysis Regions** inside the **MolTrack Workspace**.
- **Region Editing Tool** is an interaction mode, not a separate analysis workflow stage.
- An **Analysis Region** can be copied across frames without registration.
- An **Analysis Region** has one **Region Coordinate Scope**.
- A **Registered Analysis Region** is drawn in the **Registered Field of View** and projected to each frame through that frame's **Registration Shift**.
- Coverage and density for an **Analysis Region** use the frame's **Observed Region Footprint** as the measurement denominator.
- Counts, density, and row-order metrics use **Regional Detection Membership**.
- **Regional Detection Membership** is evaluated independently for each **Analysis Region**; regions do not need to form a non-overlapping partition.
- **Region Identity** links copied or edited region geometries that represent the same analytical region across frames.
- A **Region Metrics Export** uses **Region Identity** to report temporal changes for the same **Analysis Region**.
- Removing an **Analysis Region** removes its **Region Identity** from active analysis and exports.
- One **Region Identity** has one **Region Coordinate Scope**.
- A **Region Identity** may use native per-frame geometry or registered geometry, but does not mix both coordinate scopes.
- A **Region Metrics Export** retains a row for an **Analysis Region** on a frame even when its **Observed Region Footprint** has zero area.
- If the **Observed Region Footprint** has zero area, regional metrics that require observed pixels are unavailable for that row.
- Mask-based coverage uses the intersection of selected **Molecular Instance Masks** with the **Observed Region Footprint**.
- A **Terrace Region** and a **Step Edge Region** are specialisations of **Analysis Region**.
- A **Registration Shift** aligns a frame by translation only and does not locally deform molecule shapes.
- **Registration Shifts** are optional; **MolTrack** workflows can proceed without registration.
- **Registration Settings** MVP include registration method, reference mode, frame range, shift preview, and applying registration.
- **Registration Settings** MVP supports phase correlation and **Optical-Flow Translation Registration**, not local warping.
- **Optical-Flow Translation Registration** estimates X/Y translation only and does not warp image pixels.
- **Molecular Detections** may be proposed in **Native Frame Coordinates**.
- **Molecular Tracks** and regional comparisons may use **Registered Coordinates** to reduce apparent drift.
- A **Molecular Detection** stores its canonical position in **Native Frame Coordinates**.
- A registered position for a **Molecular Detection** is derived from its native position and the frame's **Registration Shift**.
- **Analysis Coordinate Context** is native when registration is not used for an analysis run.
- **Analysis Coordinate Context** is registered when registration is enabled for spatial plots, registered-region membership, and spatial metrics.
- **Analysis Coordinate Context** does not change the canonical stored **Native Frame Coordinates** of **Molecular Detections**.
- A **MolTrack Session** references exactly one **Source Image Series**.
- A **Source Image Series** must use a **Supported STM Source Format**.
- **Source Import Validation** must pass before a **MolTrack Session** is created.
- **Source Import Validation** rejects source files that cannot provide one consistent **Series Calibration** for the **Working Image Series**.
- **Source Import Validation** rejects source files with incompatible frame dimensions for one **Working Image Series**.
- A **MolTrack Session** references but does not own source pixel data from the **Source Image Series**.
- A **MolTrack Session** owns **Derived Analysis Data**.
- A **MolTrack Session** is the saved state used to continue work after closing **MolTrack**.
- A **MolTrack Session** can be saved to and loaded from a **MolTrack Session File**.
- **Session Save Command** supports Save and Save As in the MVP.
- **MolTrack** does not require autosave or session-version history in the MVP.
- Editing detections, regions, registration, frame removals, or **Analysis Settings** creates **Unsaved Session Changes**.
- Changing **Transient Workspace View State** does not create **Unsaved Session Changes**.
- **Transient Workspace View State** is not saved in the **MolTrack Session File** in the MVP.
- Creating an **Analysis Export** does not clear **Unsaved Session Changes**.
- **MolTrack** warns about **Unsaved Session Changes** before closing the workspace or replacing the loaded session.
- A **MolTrack Session File** stores **Derived Analysis Data** and source references, not full source pixel data.
- A **MolTrack Session File** stores the state needed to recompute metrics rather than treating **Analysis Metric Cache** as source of truth.
- A **MolTrack Session File** stores **Analysis Settings**.
- **Analysis Settings** include **Analysis Measurement Geometry**, **Analysis Coordinate Context**, **Row Order Analysis Settings**, and **M6 Orientation Analysis Settings**.
- **Analysis Metric Cache** may be regenerated after loading or editing a **MolTrack Session**.
- A **MolTrack Session File** stores **Source Series References** and **Lightweight Source Fingerprints**.
- When a **Source Series Reference** cannot be resolved during load, **MolTrack** asks the user to locate the same **Source Image Series**.
- **Lightweight Source Fingerprint** is used to check that relocated source files likely match the saved **MolTrack Session**.
- **Lightweight Source Fingerprint** may include file names, file sizes, modification times, frame count, image dimensions, and **Series Calibration**.
- An **Analysis Export** is generated from a **MolTrack Session** and is not the session source of truth.
- Creating an **Analysis Export** does not save or modify the **MolTrack Session File**.
- An **Analysis Export** declares its **Analysis Measurement Geometry** and does not silently mix bbox-footprint and mask-shape metrics.
- An **Analysis Export** declares its **Analysis Coordinate Context** when it reports positions or spatial metrics.
- An **Analysis Export** prioritises **Physical Molecular Metrics** when **Series Calibration** is available.
- An **Analysis Export** may include **Auxiliary Pixel Export Columns** alongside physical columns.
- **Detection Metrics Export** and **Region Metrics Export** are separate export levels.
- **BBox Detection Metrics Export** reports **Detection Identity**, **Working Frame Index**, **Source Frame Index**, regional membership, molecular position, bbox footprint size, and auxiliary pixel columns.
- **BBox Detection Metrics Export** may contain multiple rows for one **Detection Identity** when that detection has **Regional Detection Membership** in multiple overlapping **Analysis Regions**.
- If user-defined **Analysis Regions** exist and a detection has no **Regional Detection Membership**, **BBox Detection Metrics Export** keeps the detection row with no region identity.
- **BBox Detection Metrics Export** declares **Analysis Coordinate Context** and **Analysis Measurement Geometry**.
- **BBox Detection Metrics Export** is independent of whether detections have **Molecular Instance Masks**.
- **BBox Detection Metrics Export** does not include coverage, **Molecular Area**, detection status, or detector provenance.
- A **Region Metrics Export** aggregates marked detections by **Regional Detection Membership**.
- **BBox Region Metrics Export** reports frame indexes, region identity, region name, **Region Role**, observed region area, molecule count, density, footprint-size statistics, and row-order metrics.
- **BBox Region Metrics Export** counts marked detections regardless of whether they have **Molecular Instance Masks**.
- **BBox Region Metrics Export** includes row-order availability or unavailable row-order values when **Row Order Analysis Settings** cannot be satisfied.
- **BBox Region Metrics Export** does not include coverage or occupancy.
- A **MolTrack Workspace** presents one **MolTrack Session** at a time.
- **MolTrack Workspace** MVP includes **STM Image View**, **Frame Series Panel**, **Region Panel**, **Detection Panel**, **Analysis Export Panel**, and access to **MolTrack Workspace Visualizations**.
- **MolTrack Workspace Visualizations** are interactive views, not **Analysis Exports**.
- XY plots of molecular positions are **MolTrack Workspace Visualizations** in the MVP.
- XY plots support **Active-Frame XY Visualization** and **Frame-Range XY Visualization**.
- **Frame-Range XY Visualization** uses **Frame-Index Time Axis** to represent temporal progression.
- **Divisualisation-Like View** is a visualization mode inside **MolTrack Workspace Visualization**, not a separate export format.
- **Divisualisation-Like View** overlays detections from a selected frame range on one XY plot.
- **Divisualisation-Like View** may use colour or opacity to represent **Working Frame Index**.
- **Divisualisation-Like View** does not connect detections across frames with lines in the MVP because **Molecular Tracks** are deferred.
- A **Working Image Series** is derived from exactly one **Source Image Series**.
- A **Working Image Series** created from multiple source files uses **Source File Name Ordering**.
- A **Working Image Series** created from one movie file uses **Source Movie Frame Ordering**.
- A **Removed Frame** is not part of the **Working Image Series** used for detection, registration, inspection, metrics, or export.
- **Registration Shifts** are estimated over the **Working Image Series**, not over removed source frames.
- Changing the **Working Image Series** invalidates previously computed **Registration Shifts** until registration is recomputed.
- Each frame in the **Working Image Series** has a **Working Frame Index** and retains its **Source Frame Index** for provenance.
- **Frame-Index Time Axis** is the default axis for plots and exports that show molecular-field changes across frames.
- Physical timestamps may be retained when available but are not required for MolTrack analysis.

## Example Dialogue

> **Dev:** "Should the molecule row-ordering workflow become another NanoTrack panel?"
> **Domain expert:** "No — it belongs in MolTrack, because molecule detections, molecular shapes, tracks, and ordering metrics are a separate domain from NanoTrack's current nanoparticle and edge workflows."

> **Dev:** "Can we assume a molecule in frame 20 is the same molecule as the nearest detection in frame 21?"
> **Domain expert:** "Not always — some frame-to-frame changes are large enough that MolTrack should keep detections as primary observations and treat tracks as uncertain links."

> **Dev:** "Does the first MolTrack version need molecular tracks?"
> **Domain expert:** "No — the MVP should prioritise per-frame population analysis; **Molecular Tracks** can be added later as uncertain links."

> **Dev:** "Does the first MolTrack version need mask-shape analysis?"
> **Domain expert:** "No — start with **Detection-First Molecular Analysis** using marked detections and bbox-footprint metrics; mask-shape analysis can be added later."

> **Dev:** "Can MolTrack start from YOLO boxes?"
> **Domain expert:** "Yes — YOLO can mark **Molecular Detections**, and marked detections participate in analysis until they are edited or removed."

> **Dev:** "Can YOLO run over the whole series?"
> **Domain expert:** "Yes — YOLO supports active-frame, frame-range, and whole-series **Detector Frame Scope**."

> **Dev:** "Does the selected YOLO checkpoint become part of each detection?"
> **Domain expert:** "No — checkpoint selection is **Detector Run Settings**, not **Molecular Detection** source history."

> **Dev:** "Should the session remember the last YOLO dialog settings?"
> **Domain expert:** "No — **Detector Run Settings** are one-run inputs and are not saved as session state."

> **Dev:** "Which YOLO settings are visible in the MVP dialog?"
> **Domain expert:** "Show checkpoint, confidence threshold, IoU/NMS threshold, frame scope, search scope, insertion policy, and basic match-rule parameters."

> **Dev:** "Does SAM 3 use the same frame-scope concept as YOLO?"
> **Domain expert:** "Yes — but SAM 3 **Single-Frame Concept Detection** supports only active-frame **Detector Frame Scope** in the MVP."

> **Dev:** "Which SAM 3 settings are visible in the MVP dialog?"
> **Domain expert:** "Show concept prompt, optional text prompt, positive and negative **Concept Prompt Points**, confidence or probability threshold, search scope, insertion policy, and basic match-rule parameters."

> **Dev:** "After YOLO runs, does the user enter a separate correction step?"
> **Domain expert:** "No — **Detection Editing** is always available in the **MolTrack Workspace**, for example from a context menu on a molecule."

> **Dev:** "Does detection_id mean this is the same molecule in later frames?"
> **Domain expert:** "No — **Detection Identity** identifies one marked detection on one frame; cross-frame identity would be a **Molecular Track**."

> **Dev:** "If a detection is deleted, should export keep a deleted row?"
> **Domain expert:** "No — removing a **Molecular Detection** removes it and its masks from active analysis and exports."

> **Dev:** "Is a manually drawn bbox a different object type than a YOLO detection?"
> **Domain expert:** "No — manual marking and automated detectors both create **Molecular Detections**."

> **Dev:** "Can a manually drawn bbox be copied over a frame range?"
> **Domain expert:** "No — **Manual Detection Marking** creates detections on the active frame only."

> **Dev:** "Should YOLO bbox detections count in coverage?"
> **Domain expert:** "No — bbox detections provide **Detection Footprint Metrics** such as position and size; coverage requires mask-based or refined-shape geometry."

> **Dev:** "Is coverage computed over the full frame?"
> **Domain expert:** "Not necessarily — MolTrack should compute coverage over named Analysis Regions, because the experiment compares molecule fields on different terraces and around step edges."

> **Dev:** "What if the user does not draw any regions?"
> **Domain expert:** "Use a **Default Analysis Region** covering the whole observed frame, without assigning it a terrace or step-edge role."

> **Dev:** "If the user adds one terrace region, should exports still include a default whole-frame row?"
> **Domain expert:** "No — **Default Analysis Region** appears in **Region Metrics Export** only when no user-defined regions exist."

> **Dev:** "Can the user create a named ROI without saying terrace or step edge?"
> **Domain expert:** "Yes — an **Analysis Region** may have no **Region Role**."

> **Dev:** "Without registration, do regions need to be redrawn per frame?"
> **Domain expert:** "No — an Analysis Region may simply be copied to other frames with the same coordinates."

> **Dev:** "If registration creates a larger shared field of view, can I draw a terrace region there?"
> **Domain expert:** "Yes — that is a **Registered Analysis Region** drawn in the **Registered Field of View**, then projected back to each frame by its **Registration Shift**."

> **Dev:** "Can I manually add a molecule in the registered area where this frame has no pixels?"
> **Domain expert:** "No — a **Molecular Detection** must be inside the frame's **Observed Frame Footprint**."

> **Dev:** "Does an unobserved part of a registered region count against coverage on a shifted frame?"
> **Domain expert:** "No — metrics use the **Observed Region Footprint**, so pixels outside that frame's observed image are ignored."

> **Dev:** "Is regional density divided by nominal region area?"
> **Domain expert:** "No — **Molecular Density** divides count by the frame's observed region area."

> **Dev:** "If a molecule mask crosses a region boundary, which region owns the molecule?"
> **Domain expert:** "Counts use **Regional Detection Membership** from **Molecular Position**; mask coverage uses the geometric intersection of the mask with each observed region."

> **Dev:** "Can one molecule be counted in both a terrace region and a step-edge region?"
> **Domain expert:** "Yes — **Regional Detection Membership** is evaluated per region, so overlapping regions produce independent regional metrics."

> **Dev:** "If I edit a copied terrace region on frame 20, is it a new region?"
> **Domain expert:** "No — it keeps the same **Region Identity** unless the user explicitly creates a separate analysis region."

> **Dev:** "If a region is deleted, should the region export keep deleted rows?"
> **Domain expert:** "No — removing an **Analysis Region** removes its **Region Identity** from active analysis and exports."

> **Dev:** "Can the same region be native on some frames and registered on others?"
> **Domain expert:** "No — one **Region Identity** has one **Region Coordinate Scope**."

> **Dev:** "If a registered region has no observed pixels on one frame, should the export omit the row?"
> **Domain expert:** "No — keep the **Region Metrics Export** row with zero observed area and unavailable regional metrics."

> **Dev:** "Does registration change molecule area?"
> **Domain expert:** "No — the registration used here is a global XY shift, not a local warp, so it is safe as an alignment coordinate system while detections can still originate from native frames."

> **Dev:** "Does optical flow warp MolTrack frames?"
> **Domain expert:** "No — **Optical-Flow Translation Registration** estimates only global X/Y translation."

> **Dev:** "Must registration be run before detection or analysis?"
> **Domain expert:** "No — registration can be completely skipped; MolTrack should treat it as optional alignment context."

> **Dev:** "Which registration controls are visible in MVP?"
> **Domain expert:** "Show method, reference mode, frame range, shift preview, and apply registration; keep registration as global translation."

> **Dev:** "If YOLO detects on native frames but tracking uses registration, which coordinates do we save?"
> **Domain expert:** "Save Molecular Detections in Native Frame Coordinates and derive Registered Coordinates from the current Registration Shifts."

> **Dev:** "If registration is enabled for analysis, should XY plots still use native positions?"
> **Domain expert:** "No — the **Analysis Coordinate Context** becomes registered for spatial plots and metrics, while detections remain stored in native coordinates."

> **Dev:** "Is a YOLO txt export the MolTrack session?"
> **Domain expert:** "No — YOLO txt is an export; the **MolTrack Session** must retain detections, regions, registration shifts, masks, links, and metrics."

> **Dev:** "Should the MolTrack Session bundle the full source images?"
> **Domain expert:** "No — it references one **Source Image Series** and owns the **Derived Analysis Data** created from it."

> **Dev:** "What is a MolTrack session file for?"
> **Domain expert:** "It saves one **MolTrack Session** so the user can load the same source series and continue work later."

> **Dev:** "Does MolTrack need autosave for sessions in the MVP?"
> **Domain expert:** "No — **Session Save Command** with Save and Save As is enough."

> **Dev:** "Should exporting CSV clear the unsaved-changes warning?"
> **Domain expert:** "No — only **Session Save Command** clears **Unsaved Session Changes**."

> **Dev:** "Does changing frame, zoom, or pan make the session dirty?"
> **Domain expert:** "No — that is **Transient Workspace View State**, not saved analysis state."

> **Dev:** "Should the session remember zoom, pan, or the active frame?"
> **Domain expert:** "No — **Transient Workspace View State** is not saved in the MVP."

> **Dev:** "Are saved metric values the source of truth?"
> **Domain expert:** "No — session state is the source of truth; **Analysis Metric Cache** is derived and can be regenerated."

> **Dev:** "If metrics are recomputed, do analysis settings need to be saved?"
> **Domain expert:** "Yes — **Analysis Settings** are saved so recomputed metrics use the same measurement geometry, coordinate context, and row-order parameters."

> **Dev:** "What if the source STM files moved after saving the session?"
> **Domain expert:** "Use **Source Series References** and **Lightweight Source Fingerprints**; if references fail, ask the user to locate the same source series."

> **Dev:** "Does the session need to hash full source files?"
> **Domain expert:** "No — use **Lightweight Source Fingerprint** for fast matching in the MVP."

> **Dev:** "Should MolTrack open with a workflow wizard?"
> **Domain expert:** "No — it should open as a MolTrack Workspace; commands may live in side panels or menus, but the user should stay in the analysis surface."

> **Dev:** "What are the minimum workspace areas for MVP?"
> **Domain expert:** "Use **STM Image View**, **Frame Series Panel**, **Region Panel**, **Detection Panel**, **Analysis Export Panel**, and access to **MolTrack Workspace Visualizations**."

> **Dev:** "Can exported CSV files replace the MolTrack Session?"
> **Domain expert:** "No — CSV and YOLO labels are Analysis Exports generated from the session."

> **Dev:** "Does exporting CSV save the session?"
> **Domain expert:** "No — **Analysis Export** is separate from **Session Save Command**."

> **Dev:** "Is the XY molecule-position plot an export artifact?"
> **Domain expert:** "No — it is a **MolTrack Workspace Visualization**; CSV exports provide the tabular data."

> **Dev:** "Should XY visualization support only the active frame?"
> **Domain expert:** "No — support both **Active-Frame XY Visualization** and **Frame-Range XY Visualization**."

> **Dev:** "Can MolTrack include a mode inspired by Divisualisation?"
> **Domain expert:** "Yes — treat it as **Divisualisation-Like View** inside **MolTrack Workspace Visualization**, not as a separate export."

> **Dev:** "Should Divisualisation-like XY connect points between frames?"
> **Domain expert:** "No — overlay frame-range detections with colour or opacity by frame index, but do not draw cross-frame links without **Molecular Tracks**."

> **Dev:** "Can one CSV contain bbox-footprint metrics and mask-shape metrics without saying which is which?"
> **Domain expert:** "No — each **Analysis Export** declares its **Analysis Measurement Geometry**, and mixed exports must separate the metric families."

> **Dev:** "Can x_nm/y_nm be exported without saying whether they are native or registered?"
> **Domain expert:** "No — **Analysis Export** declares its **Analysis Coordinate Context** when positions or spatial metrics are reported."

> **Dev:** "Should bbox export include pixel columns?"
> **Domain expert:** "Yes — include them as **Auxiliary Pixel Export Columns**, while physical nanometer-based columns remain the primary reported metrics."

> **Dev:** "Can one export row mix a molecule detection and regional density?"
> **Domain expert:** "No — keep **Detection Metrics Export** and **Region Metrics Export** as separate levels."

> **Dev:** "What is the minimum bbox region export?"
> **Domain expert:** "Use **BBox Region Metrics Export** with frame indexes, region identity/name/role, observed area, count, density, footprint-size statistics, and row-order metrics."

> **Dev:** "What is the minimum bbox detection export?"
> **Domain expert:** "Use **BBox Detection Metrics Export** with detection id, frame indexes, regional membership, nm position, bbox footprint size, auxiliary pixel geometry, coordinate context, and measurement geometry."

> **Dev:** "If a detection belongs to two overlapping regions, does the detection export duplicate it?"
> **Domain expert:** "Yes — **BBox Detection Metrics Export** has one row per detection-region membership so overlapping regions remain independent."

> **Dev:** "Can one MolTrack Session compare multiple experiments?"
> **Domain expert:** "No — one **MolTrack Session** always contains exactly one **Source Image Series**."

> **Dev:** "Can MolTrack import PNG or TIFF images for detector tests?"
> **Domain expert:** "No — **MolTrack** only accepts **Supported STM Source Formats**: MPP, STP, and S94."

> **Dev:** "Can MolTrack create a session when source files have inconsistent nm-per-pixel?"
> **Domain expert:** "No — **Source Import Validation** requires one consistent **Series Calibration**."

> **Dev:** "When importing several STP or S94 files, how is frame order determined?"
> **Domain expert:** "Use **Source File Name Ordering** to create the **Working Image Series**."

> **Dev:** "Should frame10 sort before frame2?"
> **Domain expert:** "No — **Source File Name Ordering** is natural file-name ordering."

> **Dev:** "When importing one MPP movie, do file names affect frame order?"
> **Domain expert:** "No — use **Source Movie Frame Ordering** from the movie itself."

> **Dev:** "Does excluding a frame just hide it from analysis?"
> **Domain expert:** "No — in MolTrack a Removed Frame is treated as removed from the Working Image Series, not merely hidden."

> **Dev:** "Can a removed frame still keep detections or metrics for export?"
> **Domain expert:** "No — a **Removed Frame** is completely unavailable to downstream detection, registration, regions, metrics, and exports."

> **Dev:** "After removing frame 5, do later detections keep the old numbering?"
> **Domain expert:** "MolTrack works with Working Frame Indexes, while retaining Source Frame Indexes for provenance."

> **Dev:** "If frames are removed after registration, can old registration shifts remain valid?"
> **Domain expert:** "No — changing the **Working Image Series** invalidates **Registration Shifts** until they are recomputed."

> **Dev:** "Should field-reorganisation plots use physical timestamps by default?"
> **Domain expert:** "No — use **Frame-Index Time Axis**; physical timestamps may be metadata but are not required."

> **Dev:** "Do detections require masks before they can be measured?"
> **Domain expert:** "No — bbox detections are useful on their own for position, count, and footprint-size analysis, and masks are an optional measurement layer that can be generated later."

> **Dev:** "Does a YOLO bbox become a seed before SAM2 runs?"
> **Domain expert:** "No — it remains a Molecular Detection and is used as a Segmentation Prompt for producing a Molecular Instance Mask."

> **Dev:** "If SAM2 propagates a mask over time, is that automatically a Molecular Track?"
> **Domain expert:** "No — temporal propagation can propose masks, but identity still needs to remain uncertain when frame-to-frame changes are large."

> **Dev:** "Is SAM2 a detector in MolTrack?"
> **Domain expert:** "No — YOLO is the Molecular Detector; SAM2 is a Segmentation Backend that can turn marked detections into masks."

> **Dev:** "Can we call bbox coverage molecule area?"
> **Domain expert:** "No — bbox-derived values are **Detection Footprint Metrics**; molecule area and coverage require mask-based or refined-shape geometry."

> **Dev:** "If a molecule only has a YOLO bbox, can we export molecular area?"
> **Domain expert:** "No — export position, count, and bbox-size metrics, but reserve **Molecular Area** for mask-based or refined-shape measurements."

> **Dev:** "Can bbox width and height be described as molecule size?"
> **Domain expert:** "No — they are **Detection Footprint Size**, not a physical molecule shape measurement."

> **Dev:** "Can bbox-based regional metrics include occupancy?"
> **Domain expert:** "No — bbox-based **Region Metrics Export** excludes coverage and occupancy; those require mask-shape analysis."

> **Dev:** "Can one export silently mix bbox positions and mask centroid positions?"
> **Domain expert:** "No — each export uses one explicit **Analysis Measurement Geometry** so the reported positions and metrics have one meaning."

> **Dev:** "In mask-based analysis, do bbox-only detections still count toward density?"
> **Domain expert:** "No — mask-based count and density include only detections with a selected **Molecular Instance Mask**."

> **Dev:** "In bbox-based analysis, do masks affect count or density?"
> **Domain expert:** "No — bbox-based **Analysis Measurement Geometry** ignores masks completely."

> **Dev:** "Do we need masks before measuring row order?"
> **Domain expert:** "No — first-pass **Molecular Row Order** can be estimated from marked detection centroids."

> **Dev:** "Is row order one value for the whole experiment?"
> **Domain expert:** "No — row-order metrics are reported per **Analysis Region** and **Working Frame Index**; trends are derived across the **Frame-Index Time Axis**."

> **Dev:** "What if the molecules are only roughly aligned, not perfectly in rows?"
> **Domain expert:** "Then the user adjusts **Row Order Analysis Settings** so row-like order is measured with explicit tolerances rather than hidden fixed rules."

> **Dev:** "If a region has too few molecules for row-order analysis, should the score be zero?"
> **Domain expert:** "No — row-order metrics are unavailable when the minimum region population is not met."

> **Dev:** "If a molecule has both a bbox and a mask, which point do XY plots use?"
> **Domain expert:** "Use **Molecular Position** from the active **Measurement Geometry**: bbox center for bbox analysis and geometric mask centroid for shape analysis."

> **Dev:** "Should MolTrack report bbox positions mainly in pixels?"
> **Domain expert:** "No — **Physical Coordinates** are the primary reporting coordinates when **Source Image Calibration** is available; pixels remain auxiliary."

> **Dev:** "Can one Working Image Series mix frames with different nm-per-pixel scales?"
> **Domain expert:** "No — one **Working Image Series** has one **Series Calibration** so regions, registration, and density metrics share the same physical scale."

> **Dev:** "Should XY plots include absolute instrument offsets from the STM metadata?"
> **Domain expert:** "No — MolTrack uses **Series Physical Coordinates** for analysis; instrument offsets may remain metadata."

> **Dev:** "Should MolTrack define a new physical axis orientation?"
> **Domain expert:** "No — copy **NanoTrack Coordinate Orientation** so regions, bbox overlays, registered views, and exports use the same local image convention."

> **Dev:** "If a molecule mask crosses a region boundary, does the molecule position change per region?"
> **Domain expert:** "No — **Molecular Position** comes from the full active **Measurement Geometry**; regions only affect membership and regional coverage intersections."

> **Dev:** "If SAM 3 finds similar molecules inside a region, is that segmentation or detection?"
> **Domain expert:** "It is **Similarity-Based Molecular Detection** when it creates new molecule observations; any masks it returns remain candidate **Molecular Instance Masks** until selected for mask-based measurement."

> **Dev:** "Can we keep SAM2 and micro-SAM masks for the same molecule?"
> **Domain expert:** "Yes — a **Molecular Detection** may have multiple candidate **Molecular Instance Masks**, but mask-based metrics use the selected measurement mask."

> **Dev:** "Do molecule masks need to be saved as full-frame bitmaps?"
> **Domain expert:** "No — store them as **Local Instance Masks** tied to the detection footprint and reconstruct full-frame overlays only when needed."

> **Dev:** "If I change the SAM probability threshold, is it still the same mask?"
> **Domain expert:** "No — the threshold is part of **Mask Provenance**, so the resulting candidate mask is a distinct measurement candidate."

> **Dev:** "If SAM2 fails to find a mask for a bbox, should we create a new detection for another attempt?"
> **Domain expert:** "No — run a **Segmentation Retry** on the same **Molecular Detection** with adjusted prompts or settings."

> **Dev:** "Can we test SAM 3 concept prompting by giving one example molecule on a single image?"
> **Domain expert:** "Yes — treat that as **Single-Frame Concept Detection**, producing marked **Molecular Detections** and optional candidate masks on that frame."

> **Dev:** "Do positive and negative SAM 3 prompt points count as detections?"
> **Domain expert:** "No — they are **Concept Prompt Points** that guide **Single-Frame Concept Detection**; only produced **Molecular Detections** participate in analysis."

> **Dev:** "Are SAM 3 prompt points saved in the session?"
> **Domain expert:** "No — **Concept Prompt Points** are temporary detector-run inputs."

> **Dev:** "Are SAM 3 image exemplars saved in the session?"
> **Domain expert:** "No — image exemplars in a **Molecule Concept Prompt** are temporary detector-run inputs."

> **Dev:** "Can Single-Frame Concept Detection run on a standalone PNG?"
> **Domain expert:** "No — it runs on one **Working Frame Index** from the loaded STM source series."

> **Dev:** "Should SAM 3 concept detection run over a whole frame range in the MVP?"
> **Domain expert:** "No — **Single-Frame Concept Detection** runs on the active frame only."

> **Dev:** "If regions exist, can a detector still search the whole frame?"
> **Domain expert:** "Yes — **Whole-Frame Detection Search Scope** remains available even when user-defined regions exist."

> **Dev:** "If there are no regions, should detector UI show a synthetic Default Analysis Region?"
> **Domain expert:** "No — use **Whole-Frame Detection Search Scope**; **Default Analysis Region** is an analysis fallback."

> **Dev:** "Does whole-frame detection search the entire registered canvas?"
> **Domain expert:** "No — **Whole-Frame Detection Search Scope** searches the frame's **Observed Frame Footprint**."

> **Dev:** "Can one detector run search several regions at once?"
> **Domain expert:** "No — a detector run uses one **Detection Search Scope** at a time."

> **Dev:** "Must users draw terrace regions before running YOLO?"
> **Domain expert:** "No — detections can be created first, and **Regional Detection Membership** is recalculated when **Analysis Regions** are later added or edited."

> **Dev:** "Does region editing require a separate workflow stage?"
> **Domain expert:** "No — use a **Region Editing Tool** inside the **MolTrack Workspace**."

> **Dev:** "If YOLO runs on a cropped terrace region, are detections stored relative to the crop?"
> **Domain expert:** "No — all **Molecular Detections** are stored in working-frame coordinates regardless of **Detection Search Scope**."

> **Dev:** "If SAM 3 finds a molecule that YOLO already marked, should MolTrack count both?"
> **Domain expert:** "No — the detector run uses a **Detection Insertion Policy**; by default overlapping proposals merge with existing detections instead of creating duplicate molecule counts."

> **Dev:** "How does MolTrack know whether a new bbox is the same molecule as an existing bbox?"
> **Domain expert:** "Use a **Detection Match Rule** with visible parameters such as bbox overlap and centroid distance; if masks exist, mask overlap may refine the match."

## Flagged Ambiguities

- "new app" was resolved as **MolTrack**, a separate application context, not a NanoTrack mode.
- "track" was resolved as an optional, uncertain interpretation rather than guaranteed molecular identity across all frames.
- "tracking MVP" was rejected; **Molecular Tracks** are deferred behind per-frame population analysis.
- "mask-shape MVP" was rejected; the initial MolTrack workflow is **Detection-First Molecular Analysis**.
- "analysis" was resolved as **Molecular Population Analysis** first, with individual **Molecular Tracks** as optional secondary evidence.
- "review status" was removed from the MolTrack vocabulary; a **Molecular Detection** participates in analysis while it remains marked.
- "manual correction step" was rejected; **Detection Editing** is always available in the **MolTrack Workspace**.
- "detection_id as track identity" was rejected; **Detection Identity** is per detection on one frame.
- "deleted detection status" was rejected; removed **Molecular Detections** leave active analysis and exports.
- "YOLO checkpoint as detection history" was rejected; checkpoint selection is **Detector Run Settings**.
- "saved detector UI preferences" were rejected; **Detector Run Settings** are not saved as session state.
- "hidden YOLO thresholds" were rejected for MVP; core YOLO **Detector Run Settings** are user-visible.
- "YOLO frame scope" was resolved as active frame, frame range, or whole **Working Image Series**.
- "SAM 3 frame scope" was resolved as active-frame-only **Detector Frame Scope** for MVP.
- "hidden SAM 3 threshold" was rejected for MVP; SAM 3 confidence or probability threshold is part of **Detector Run Settings**.
- "SAM 3 positive/negative points" were resolved as **Concept Prompt Points**, not **Molecular Detections**.
- "saved SAM 3 prompt points" were rejected; **Concept Prompt Points** are temporary detector-run inputs.
- "saved SAM 3 image exemplars" were rejected; image exemplars are temporary detector-run inputs.
- "manual vs automatic detection" was resolved as the same **Molecular Detection** concept with different provenance.
- "manual detection propagation" was rejected for MVP; **Manual Detection Marking** is active-frame only.
- "field" and "step" were resolved into named **Analysis Regions**, especially **Terrace Region** and **Step Edge Region**.
- "no region defined" was resolved as a **Default Analysis Region** over the whole observed frame, not as a terrace or step-edge role.
- "default region alongside user regions" was rejected; **Default Analysis Region** is used only when no user-defined regions exist.
- "required region type" was rejected; an **Analysis Region** may have no **Region Role**.
- "region over time" was resolved as copyable across frames, not necessarily a per-frame edited shape.
- "region relative to the registered image" was resolved as a **Registered Analysis Region** in the **Registered Field of View**.
- "detection outside image pixels" was rejected; a **Molecular Detection** must lie inside the frame's **Observed Frame Footprint**.
- "missing pixels inside a registered region" were resolved as outside the **Observed Region Footprint** for that frame.
- "density over nominal unobserved area" was rejected; **Molecular Density** uses observed analysis area.
- "detection in region" was resolved as **Regional Detection Membership** based on **Molecular Position**, not bbox or mask overlap.
- "overlapping regions" were resolved as independent **Analysis Regions**, not a required non-overlapping partition.
- "region geometry as identity" was rejected; copied or edited regions can retain **Region Identity** across frames.
- "deleted region status" was rejected; removed **Analysis Regions** leave active analysis and exports.
- "mixed coordinate-scope region" was rejected; one **Region Identity** has one **Region Coordinate Scope**.
- "region row omission for zero observed area" was rejected; **Region Metrics Export** keeps the row with unavailable metrics.
- "ignore region" was removed from the current MolTrack vocabulary and deferred as a possible future extension.
- "optical flow" was resolved as **Optical-Flow Translation Registration**, not image warping.
- "registration" was resolved as optional, not a required preprocessing stage.
- "advanced local registration controls" were rejected for MVP; **Registration Settings** compute global translation shifts.
- "registered bbox" was resolved as a derived view, not the canonical stored position of a **Molecular Detection**.
- "registered analysis positions" were resolved as **Analysis Coordinate Context**, not canonical detection storage.
- "project" was corrected to **MolTrack Session**, a saved/loadable state for one source series, not a multi-series project container.
- "save/load current work" was resolved as **MolTrack Session File**.
- "session autosave/versioning" was rejected for MVP; **Session Save Command** supports Save and Save As.
- "export clears dirty state" was rejected; only **Session Save Command** clears **Unsaved Session Changes**.
- "view navigation as dirty state" was rejected; **Transient Workspace View State** does not create **Unsaved Session Changes**.
- "saved view state" was rejected for MVP; **Transient Workspace View State** is not saved.
- "saved metrics as source of truth" was rejected; metrics are recomputed from session state or treated as **Analysis Metric Cache**.
- "export as save" was rejected; **Analysis Export** is separate from **Session Save Command**.
- "saved plot report" was rejected for MVP; XY plots are **MolTrack Workspace Visualizations**.
- "single-mode XY plot" was rejected; MolTrack supports active-frame and frame-range XY visualizations.
- "Divisualisation-like mode" was accepted as a planned **MolTrack Workspace Visualization** style requiring precise interaction details.
- "cross-frame XY lines without tracks" were rejected; **Divisualisation-Like View** does not imply **Molecular Tracks**.
- "workflow wizard as main UI" was rejected; MVP uses a **MolTrack Workspace** with image, frame, region, detection, analysis/export, and visualization areas.
- "unsaved analysis settings" were rejected; **Analysis Settings** are saved in the **MolTrack Session File**.
- "moved source files" were resolved with **Source Series References** and **Lightweight Source Fingerprints**, not by bundling full images.
- "full-file source hashing" was rejected as the default MVP fingerprint strategy.
- "session scope" was resolved as exactly one **Source Image Series** per **MolTrack Session**.
- "generic image import" was rejected; **MolTrack** accepts only **Supported STM Source Formats**.
- "best-effort import with inconsistent calibration" was rejected; **Source Import Validation** blocks session creation.
- "multi-file frame order" was resolved as **Source File Name Ordering**.
- "lexicographic source ordering" was rejected; **Source File Name Ordering** is natural ordering.
- "MPP frame order" was resolved as **Source Movie Frame Ordering**.
- "exclude frame" was resolved as **Removed Frame**, meaning removal from the **Working Image Series**, not a soft analysis filter.
- "registration after removing frames" was resolved as registration over the **Working Image Series** only.
- "registration after Working Image Series changes" was resolved as invalidated until recomputed.
- "frame index" was split into **Working Frame Index** and **Source Frame Index**.
- "time axis" was resolved as **Frame-Index Time Axis**, not required physical timestamps.
- "bbox coverage" was rejected; bbox analysis is **Detection Footprint Metrics**, while coverage requires mask-based or refined-shape geometry.
- "bbox occupancy" was rejected together with bbox coverage for bbox-based **Region Metrics Export**.
- "bbox mode" and "shape mode" were resolved as choices of **Measurement Geometry**, not separate analysis types.
- "masks affecting bbox analysis" was rejected; bbox-based **Analysis Measurement Geometry** is independent of masks.
- "mixed geometry export" was rejected; **Analysis Measurement Geometry** is explicit per analysis run or export.
- "ambiguous export coordinates" were rejected; **Analysis Export** declares **Analysis Coordinate Context**.
- "mixed export granularity" was rejected; **Detection Metrics Export** and **Region Metrics Export** are separate levels.
- "bbox detection export with coverage/status/provenance" was rejected; **BBox Detection Metrics Export** reports bbox-footprint metrics only.
- "single detection export row despite overlapping regions" was rejected; **BBox Detection Metrics Export** expands by regional membership.
- "bbox region export with coverage/occupancy" was rejected; **BBox Region Metrics Export** reports count, density, footprint statistics, and row-order metrics.
- "area from bbox" was resolved as footprint or bbox-size analysis, not **Molecular Area**.
- "bbox size as molecule size" was rejected; bbox dimensions are **Detection Footprint Size**.
- "pixel metrics as default" was rejected; MolTrack prioritises **Physical Molecular Metrics** from **Source Image Calibration**.
- "pixel columns in export" were accepted only as **Auxiliary Pixel Export Columns**, not primary metrics.
- "per-frame physical scale" was rejected for one **Working Image Series**; MolTrack expects one **Series Calibration**.
- "absolute instrument offsets" were rejected as the default analysis origin; MolTrack uses **Series Physical Coordinates**.
- "MolTrack-specific axis orientation" was rejected; MolTrack reuses **NanoTrack Coordinate Orientation**.
- "SAM 3/FastSAM/YOLO-SAM as alternatives to YOLO" was resolved as **Similarity-Based Molecular Detection** when they propose new molecule observations.
- "SAM3+Adapter" was corrected to SAM 3 concept prompting as described by the Ultralytics SAM 3 workflow.
- "SAM 3 on one image" was resolved as **Single-Frame Concept Detection**, not tracking.
- "SAM 3 standalone image test" was rejected; **Single-Frame Concept Detection** uses a loaded **Working Frame Index**.
- "SAM 3 batch concept detection" was rejected for MVP; **Single-Frame Concept Detection** runs on the active frame only.
- "detector run area" was resolved as **Detection Search Scope**, separate from metric grouping by **Analysis Region**.
- "visible default detector region" was rejected; detector UI uses **Whole-Frame Detection Search Scope** when no regions exist.
- "whole-frame detection on registered canvas" was rejected; **Whole-Frame Detection Search Scope** means the frame's **Observed Frame Footprint**.
- "multi-region detector run" was rejected for MVP; a detector run uses one **Detection Search Scope** at a time.
- "detector-specific search rules" were rejected; **Detection Search Scope** applies to all molecular detectors.
- "rerunning detectors" was resolved with **Detection Insertion Policy**, not detection review statuses.
- "same molecule from two detector runs" was resolved with **Detection Match Rule**, not detector source priority alone.
- "detection history/provenance" was rejected for current MolTrack; marked **Molecular Detections** do not need source history to participate in analysis.
- "mask history/provenance" remains minimal **Mask Provenance** because segmentation settings can create multiple candidate masks for one **Molecular Detection**.
- "regions before detection" was rejected as a requirement; regions may be added after detections and metrics recalculated.
- "region editing workflow stage" was rejected; region editing is a **Region Editing Tool** in the workspace.
- "mask without detection" was rejected; every **Molecular Instance Mask** belongs to a parent **Molecular Detection**.
- "full-frame molecule masks" were rejected for current storage; molecule masks use **Local Instance Masks**.
- "SAM probability threshold" was resolved as part of **Segmentation Settings** and **Mask Provenance**.
- "failed mask generation" was resolved as a **Segmentation Retry** on the same **Molecular Detection**, not a new detection.
- "position" was resolved as **Molecular Position** derived from the active **Measurement Geometry**.
- "imperfect rows" were resolved as row-like arrangements measured under explicit **Row Order Analysis Settings**.
- "too few molecules for row order" was resolved as unavailable row-order metrics, not zero row order.
- "order" was resolved first as centroid-based **Molecular Row Order**, with image FFT/structure-factor methods left as later analysis extensions.
- "row-order trend as separate entity" was rejected; trends are derived from per-region, per-frame row-order metrics.
- "seed" was avoided in MolTrack segmentation; the canonical term is **Segmentation Prompt**.
- "segmentation" was split into **Frame Segmentation** and **Temporal Mask Propagation**.
