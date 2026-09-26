import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { EventEvidenceResponse } from "../api/types";
import { EvidencePanel } from "./EvidencePanel";

const evidence: EventEvidenceResponse = {
  source_event_id: "volve_ddr:15_9_F_1_2013_08_23:act023",
  event_type: "stuck_pipe",
  well_id: "15/9-F-1",
  wellbore_id: "15/9-F-1",
  occurred_at: "2013-08-22",
  depth_md_m: 2601,
  depth_tvd_m: null,
  evidence_type: "verbatim_source_text",
  evidence_text: 'Stuck with flex stab in 13 3/8" shoe, stab 5 m behind bit.',
  source_location: "15_9_F_1_2013_08_23 activity 2013-08-22T22:30:00+02:00..2013-08-22T23:00:00+02:00",
  source: "volve_ddr_hf_derivative",
  confidence: 1.0,
  provenance: {
    original_corpus: "Equinor Volve Daily Drilling Reports (original format: WITSML DrillReport)",
    derivative_dataset: "bengsoon/volve_daily_drilling_report",
    derivative_is_original_source: false,
    source_document_id: "doc-1",
    source_document_title: "Volve DDR 15_9_F_1_2013_08_23 (public derivative, not the original WITSML file)",
    source_document_uri: "hf://bengsoon/volve_daily_drilling_report#docName=15_9_F_1_2013_08_23",
  },
  disclaimer: "Evidence text is copied verbatim from the audited public derivative... not the original Equinor WITSML file itself.",
};

describe("EvidencePanel", () => {
  it("prompts to select an event when idle", () => {
    render(<EvidencePanel evidenceState={{ status: "idle" }} />);
    expect(screen.getByText(/select a historical event/i)).toBeInTheDocument();
  });

  it("shows an error state, never fake evidence, when the request fails", () => {
    render(<EvidencePanel evidenceState={{ status: "error", message: "not found" }} />);
    expect(screen.getByText(/evidence unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/stuck with flex stab/i)).not.toBeInTheDocument();
  });

  it("renders the exact verbatim source text, unrewritten", () => {
    render(<EvidencePanel evidenceState={{ status: "success", data: evidence }} />);
    expect(screen.getByText(`"${evidence.evidence_text}"`)).toBeInTheDocument();
    expect(screen.getByText("Verbatim source text")).toBeInTheDocument();
    expect(screen.getByText(evidence.provenance.source_document_title!)).toBeInTheDocument();
  });

  it("labels metadata-only evidence distinctly and never fabricates missing text", () => {
    const metadataOnly: EventEvidenceResponse = { ...evidence, evidence_type: "metadata_only", evidence_text: null };
    render(<EvidencePanel evidenceState={{ status: "success", data: metadataOnly }} />);
    expect(screen.getByText("Metadata only")).toBeInTheDocument();
    expect(screen.getByText(/no verbatim source text captured/i)).toBeInTheDocument();
  });

  it("always surfaces the provenance disclaimer", () => {
    render(<EvidencePanel evidenceState={{ status: "success", data: evidence }} />);
    expect(screen.getByText(evidence.disclaimer)).toBeInTheDocument();
  });
});
