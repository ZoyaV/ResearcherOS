/** Built-in demo project used by the standalone web preview. */
const DEMO = {
  id: "demo-aggregation",
  title: "Unstable recombinant protein expression",
  nodes: [
    { id: "n-problem", parent_id: null, node_type: "problem", title: "Low target-protein yield in HEK293 culture", has_kanban: false },
    { id: "n-cause-misfold", parent_id: "n-problem", node_type: "cause", title: "Cause: aggregation due to misfolding", has_kanban: false },
    { id: "n-cause-toxic", parent_id: "n-problem", node_type: "cause", title: "Cause: cellular toxicity", has_kanban: false },
    { id: "n-ev-viability", parent_id: "n-cause-toxic", node_type: "cause_evidence", title: "Evidence: 72-hour viability assay", has_kanban: true, board_id: "board-ev-viability" },
    { id: "n-ev-fold", parent_id: "n-cause-misfold", node_type: "cause_evidence", title: "Evidence: ThT fluorescence and inclusion TEM", has_kanban: true, board_id: "board-ev-fold" },
    { id: "n-rem-chaperone", parent_id: "n-cause-misfold", node_type: "remediation", title: "Remediation: HSP70/40 chaperone co-expression", has_kanban: true, board_id: "board-rem-chaperone" },
    { id: "n-exp-tht", parent_id: "n-ev-fold", node_type: "experiment", title: "ThT assay on 24/48/72-hour lysates", has_kanban: false },
  ],
  boards: {
    "board-ev-fold": {
      owner_node_id: "n-ev-fold",
      columns: [
        { id: "backlog", title: "Backlog" },
        { id: "running", title: "Running" },
        { id: "done", title: "Done" },
        { id: "successful", title: "Successful" },
      ],
      cards: [
        { id: "c1", column_id: "backlog", title: "ThT time course", description: "Compare with the GFP control." },
        { id: "c2", column_id: "backlog", title: "Inclusion TEM", description: "n=3 biological replicates." },
      ],
    },
    "board-ev-viability": {
      owner_node_id: "n-ev-viability",
      columns: [
        { id: "backlog", title: "Backlog" },
        { id: "running", title: "Running" },
        { id: "done", title: "Done" },
        { id: "successful", title: "Successful" },
      ],
      cards: [
        { id: "c4", column_id: "backlog", title: "MTT / Trypan blue", description: "Compare with the empty vector." },
      ],
    },
    "board-rem-chaperone": {
      owner_node_id: "n-rem-chaperone",
      columns: [
        { id: "backlog", title: "Backlog" },
        { id: "running", title: "Running" },
        { id: "done", title: "Done" },
        { id: "successful", title: "Successful" },
      ],
      cards: [
        { id: "c3", column_id: "running", title: "HSP70 co-transfection", description: "1:1 and 1:2 dosage." },
      ],
    },
  },
};

const TYPE_LABELS = {
  problem: "Problem",
  cause: "Cause",
  cause_evidence: "Evidence",
  remediation: "Remediation",
  experiment: "Experiment",
};
