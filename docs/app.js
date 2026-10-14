/* Guided month-end update. One primary action on each step. */
"use strict";

(function () {
  var pipeline = window.BrokeragePipeline;
  var app = document.getElementById("app");
  var fileInput = document.getElementById("statement-file");

  var state = {
    step: 1,
    source: null,
    fileName: "",
    activity: null,
    ledger: null,
    ytd: null,
    result: null,
    error: "",
    saved: false,
    busy: false,
  };

  var STEPS = ["Load", "Run", "Results", "Download"];
  var ACTIVITY_COLUMNS = ["date", "entity", "account", "activity_type", "description", "amount"];

  var CATEGORY_LABELS = {
    wire: "Wire",
    ach: "ACH",
    contribution: "Contribution",
    distribution: "Distribution",
    cash_transfer: "Cash transfer",
    security_transfer: "Security transfer",
    margin_paydown: "Margin paydown",
    possible_transfer: "Possible transfer",
  };

  var FLAG_LABELS = {
    LARGE_AMOUNT: "Large amount",
    INTER_ENTITY: "Between the two entities",
    MISSING_COUNTERPARTY: "No counterparty",
    AMBIGUOUS_TYPE: "Type is unclear",
    KEYWORD_CLASSIFIED: "Taken from the description",
    SECURITY_WITHOUT_QTY: "No share quantity",
    MISSING_STATEMENT_VALUE: "Blank on the statement",
    INCOME_SIGN_UNEXPECTED: "Income came out positive",
    PRIOR_INCOME_NOT_CREDIT: "Prior income is not a credit",
    UNBALANCED_BEFORE_PLUG: "Needed a suspense line",
    LARGE_PLUG: "Large suspense amount",
  };

  function esc(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function money(amount) {
    return esc(pipeline.formatDollars(amount));
  }

  function friendlyError(err) {
    var msg = err && err.message ? err.message : "The update could not finish.";
    if (/unmasked|masked account/i.test(msg)) {
      return "Use masked accounts like ****1234. This file has a full number.";
    }
    if (/email/i.test(msg)) {
      return "Remove email addresses from the file.";
    }
    if (/taxpayer/i.test(msg)) {
      return "Remove taxpayer IDs from the file.";
    }
    if (/cents|whole-dollar|whole dollars/i.test(msg)) {
      return "Use whole dollar amounts only, with no cents.";
    }
    if (/not a known demo type/i.test(msg)) {
      return "One row has an activity type this update does not recognize.";
    }
    if (/dummy catalog|dummy GL|gl_code/i.test(msg)) {
      return "The books have an account code outside the sample chart of accounts.";
    }
    return msg;
  }

  function reasons(flags) {
    var labels = [];
    for (var i = 0; i < flags.length; i++) {
      if (flags[i] === "NEEDS_HUMAN_REVIEW") continue;
      labels.push(FLAG_LABELS[flags[i]] || flags[i]);
    }
    return labels.join(". ");
  }

  function counterparty(line) {
    if (line.counterparty_entity && line.counterparty_account) {
      return line.counterparty_entity + " " + line.counterparty_account;
    }
    return line.counterparty_entity || line.counterparty_account || "";
  }

  function reviewCount(transfers) {
    var count = 0;
    for (var i = 0; i < transfers.lines.length; i++) {
      if (transfers.lines[i].record_action === "REVIEW") count += 1;
    }
    return count;
  }

  function flippedCount(rows) {
    var count = 0;
    for (var i = 0; i < rows.length; i++) if (rows[i].sign_flipped) count += 1;
    return count;
  }

  function missingCount(rows) {
    var count = 0;
    for (var i = 0; i < rows.length; i++) if (rows[i].missing_statement) count += 1;
    return count;
  }

  async function loadSample() {
    var names = ["statement_activity.csv", "gl_ledger.csv", "statement_ytd.csv"];
    var texts = await Promise.all(
      names.map(function (name) {
        return fetch("fixtures/" + name).then(function (response) {
          if (!response.ok) throw new Error("missing " + name);
          return response.text();
        });
      })
    );
    return {
      activity: pipeline.parseCsv(texts[0]),
      ledger: pipeline.parseCsv(texts[1]),
      ytd: pipeline.parseCsv(texts[2]),
    };
  }

  function validateActivity(rows) {
    if (!rows.length) throw new Error("The file has no rows.");
    var header = rows[0];
    var missing = ACTIVITY_COLUMNS.filter(function (name) {
      return !Object.prototype.hasOwnProperty.call(header, name);
    });
    if (missing.length) {
      throw new Error(
        "This file is missing " +
          (missing.length === 1 ? "a column: " : "columns: ") +
          missing.join(", ") +
          "."
      );
    }
  }

  function render() {
    app.innerHTML =
      '<ol class="steps">' +
      STEPS.map(function (label, index) {
        var n = index + 1;
        return (
          '<li class="' +
          (n === state.step ? "current" : "") +
          '"' +
          (n === state.step ? ' aria-current="step"' : "") +
          '><span class="num">' +
          n +
          "</span> " +
          label +
          "</li>"
        );
      }).join("") +
      "</ol>" +
      '<section class="panel">' +
      body() +
      "</section>";
    var title = document.getElementById("step-title");
    if (title) title.focus();
  }

  function body() {
    if (state.step === 1) return stepLoad();
    if (state.step === 2) return stepRun();
    if (state.step === 3) return stepResults();
    return stepDownload();
  }

  function errorBlock() {
    if (!state.error) return "";
    return '<p class="error" role="alert">' + esc(state.error) + "</p>";
  }

  function stepLoad() {
    var chosen = state.source === "upload" && state.activity;
    var primary = chosen
      ? '<button class="primary" type="button" data-action="continue-upload"' +
        (state.busy ? " disabled" : "") +
        ">Use this statement</button>"
      : '<button class="primary" type="button" data-action="use-sample"' +
        (state.busy ? " disabled" : "") +
        ">Use the sample statement</button>";
    var alt = chosen
      ? '<p class="alt"><button class="link" type="button" data-action="use-sample">Use the sample instead</button></p>'
      : '<p class="alt"><button class="link" type="button" data-action="pick-file">Upload a statement instead</button></p>';
    var fileLine = chosen ? '<p class="file-name">' + esc(state.fileName) + "</p>" : "";
    return (
      '<h2 id="step-title" tabindex="-1">Load the statement</h2>' +
      '<p class="lead">Use the sample August statement, or upload a statement in the same format.</p>' +
      '<p class="hint">Same columns as the sample: date, entity, account, activity_type, description, amount.</p>' +
      fileLine +
      errorBlock() +
      '<div class="actions">' +
      primary +
      alt +
      "</div>"
    );
  }

  function stepRun() {
    var statementLabel =
      state.source === "upload"
        ? esc(state.fileName) + " (" + state.activity.length + " lines)"
        : "Sample (" + state.activity.length + " lines)";
    var booksNote =
      state.source === "upload"
        ? '<p class="note">Only the statement was replaced. Balances still use the sample books.</p>'
        : "";
    return (
      '<h2 id="step-title" tabindex="-1">Run the update</h2>' +
      '<p class="lead">Run the update to list money movement, line up balances, and write the journal.</p>' +
      '<dl class="facts">' +
      "<dt>Statement</dt><dd>" +
      statementLabel +
      "</dd>" +
      "<dt>Ledger</dt><dd>Sample (" +
      state.ledger.length +
      " accounts)</dd>" +
      "<dt>Year-to-date</dt><dd>Sample (" +
      state.ytd.length +
      " rows)</dd>" +
      "</dl>" +
      booksNote +
      errorBlock() +
      '<div class="actions"><button class="primary" type="button" data-action="run"' +
      (state.busy ? " disabled" : "") +
      ">Run the update</button></div>" +
      '<p class="alt"><button class="back" type="button" data-action="back">Back</button></p>'
    );
  }

  function stepResults() {
    var result = state.result;
    var transfers = result.transfers;
    var ytd = result.ytd;
    var journal = result.journal;
    var summary =
      '<div class="summary">' +
      "<p>Transfers to record: " +
      transfers.lines.length +
      ". To review: " +
      reviewCount(transfers) +
      ". Ordinary lines skipped: " +
      transfers.skippedOrdinary +
      ".</p>" +
      "<p>Balance rows: " +
      ytd.rows.length +
      ". Sign-flipped income rows: " +
      flippedCount(ytd.rows) +
      ". Blanks set to 0: " +
      missingCount(ytd.rows) +
      ".</p>" +
      "<p>Journal lines: " +
      journal.lines.length +
      ". Debits " +
      money(journal.totalDebit) +
      ". Credits " +
      money(journal.totalCredit) +
      ". Suspense " +
      money(journal.plugAmount) +
      ".</p>" +
      "</div>";
    return (
      '<h2 id="step-title" tabindex="-1">Review the results</h2>' +
      '<p class="lead">Review the transfers, the balance column, and the journal.</p>' +
      summary +
      transfersTable(transfers) +
      ytdTable(ytd) +
      journalTable(journal) +
      '<div class="actions"><button class="primary" type="button" data-action="next">Continue</button></div>' +
      '<p class="alt"><button class="back" type="button" data-action="back">Back</button></p>'
    );
  }

  function transfersTable(transfers) {
    var rows = transfers.lines
      .map(function (line) {
        var review = line.record_action === "REVIEW";
        var why = reasons(line.flags);
        return (
          '<tr class="' +
          (review ? "review" : "") +
          '"><td class="date">' +
          esc(line.date) +
          "</td><td>" +
          esc(line.entity) +
          "</td><td>" +
          esc(CATEGORY_LABELS[line.category] || line.category) +
          '<span class="sub">' +
          esc(line.description) +
          "</span></td><td class=\"num\">" +
          money(line.amount) +
          "</td><td>" +
          esc(counterparty(line)) +
          "</td><td>" +
          (review ? '<span class="review-word">Review</span>' : "Record") +
          (why ? '<span class="sub">' + esc(why) + "</span>" : "") +
          "</td></tr>"
        );
      })
      .join("");
    if (!rows) rows = '<tr><td colspan="6">No transfers to record.</td></tr>';
    return (
      '<div class="block"><h3 id="transfers-heading">Transfers</h3>' +
      '<div class="table-wrap"><table aria-labelledby="transfers-heading"><thead><tr>' +
      "<th>Date</th><th>Entity</th><th>What</th><th class=\"num\">Amount</th><th>Counterparty</th><th>Action</th>" +
      "</tr></thead><tbody>" +
      rows +
      "</tbody></table></div>" +
      '<p class="note">This list does not change the balances.</p></div>'
    );
  }

  function ytdTable(ytd) {
    var rows = ytd.rows
      .map(function (row) {
        var notes = [];
        if (row.sign_flipped) notes.push("Sign flipped");
        if (row.missing_statement) notes.push("Blank, treated as 0");
        var extra = reasons(row.flags.filter(function (flag) {
          return flag !== "MISSING_STATEMENT_VALUE";
        }));
        if (extra) notes.push(extra);
        return (
          "<tr><td>" +
          row.row_order +
          "</td><td>" +
          esc(row.entity) +
          "</td><td>" +
          row.gl_code +
          " " +
          esc(row.gl_name) +
          "</td><td class=\"num\">" +
          money(row.prior_ledger) +
          "</td><td class=\"num\">" +
          money(row.statement_ytd_raw) +
          "</td><td class=\"num\">" +
          money(row.statement_ytd_mapped) +
          "</td><td class=\"num\">" +
          money(row.difference) +
          "</td><td>" +
          esc(notes.join(". ")) +
          "</td></tr>"
        );
      })
      .join("");
    return (
      '<div class="block"><h3 id="ytd-heading">Balance column</h3>' +
      '<div class="table-wrap"><table aria-labelledby="ytd-heading"><thead><tr>' +
      "<th>Row</th><th>Entity</th><th>Account</th><th class=\"num\">Prior</th>" +
      "<th class=\"num\">Statement</th><th class=\"num\">For the books</th><th class=\"num\">Change</th><th>Note</th>" +
      "</tr></thead><tbody>" +
      rows +
      "</tbody></table></div>" +
      '<p class="note">Blank statement amounts are treated as 0. Income and gain accounts are sign-flipped.</p></div>'
    );
  }

  function journalTable(journal) {
    var rows = journal.lines
      .map(function (line) {
        return (
          '<tr class="' +
          (line.is_balancing ? "review" : "") +
          '"><td>' +
          line.line +
          "</td><td>" +
          esc(line.entity) +
          "</td><td>" +
          line.gl_code +
          " " +
          esc(line.gl_name) +
          "</td><td class=\"num\">" +
          money(line.debit) +
          "</td><td class=\"num\">" +
          money(line.credit) +
          "</td><td>" +
          (line.is_balancing ? esc(line.memo) : "") +
          "</td></tr>"
        );
      })
      .join("");
    return (
      '<div class="block"><h3 id="journal-heading">Journal</h3>' +
      '<div class="table-wrap"><table aria-labelledby="journal-heading"><thead><tr>' +
      "<th>Line</th><th>Entity</th><th>Account</th><th class=\"num\">Debit</th><th class=\"num\">Credit</th><th>Memo</th>" +
      "</tr></thead><tbody>" +
      rows +
      "</tbody></table></div>" +
      '<p class="note">Each entity balances on its own. Suspense is the change the statement does not explain.</p></div>'
    );
  }

  function stepDownload() {
    var items = pipeline.OUTPUT_NAMES.map(function (name) {
      return "<li>" + esc(name) + "</li>";
    }).join("");
    return (
      '<h2 id="step-title" tabindex="-1">Download the files</h2>' +
      '<p class="lead">Download the files from this run.</p>' +
      "<p class=\"hint\">month-end-output.zip contains:</p>" +
      '<ul class="files">' +
      items +
      "</ul>" +
      (state.saved ? '<p class="saved">Saved month-end-output.zip.</p>' : "") +
      '<div class="actions"><button class="primary" type="button" data-action="download">Download the files</button></div>' +
      '<p class="alt"><button class="back" type="button" data-action="back">Back</button></p>'
    );
  }

  async function continueUpload() {
    state.busy = true;
    state.error = "";
    render();
    try {
      if (!state.ledger || !state.ytd) {
        var sample = await loadSample();
        state.ledger = sample.ledger;
        state.ytd = sample.ytd;
      }
      state.result = null;
      state.saved = false;
      state.step = 2;
      state.error = "";
    } catch (err) {
      state.error = "The sample books did not load. Refresh the page and try again.";
    } finally {
      state.busy = false;
      render();
    }
  }

  async function useSample() {
    state.busy = true;
    state.error = "";
    render();
    try {
      var sample = await loadSample();
      state.source = "sample";
      state.fileName = "";
      state.activity = sample.activity;
      state.ledger = sample.ledger;
      state.ytd = sample.ytd;
      state.result = null;
      state.saved = false;
      state.step = 2;
      state.error = "";
    } catch (err) {
      state.error = "The sample statement did not load. Refresh the page and try again.";
    } finally {
      state.busy = false;
      render();
    }
  }

  function runUpdate() {
    state.error = "";
    try {
      state.result = pipeline.buildOutputFiles(state.activity, state.ledger, state.ytd);
      state.saved = false;
      state.step = 3;
    } catch (err) {
      state.error = friendlyError(err);
    }
    render();
  }

  function download() {
    var bytes = pipeline.createZip(state.result.files);
    var blob = new Blob([bytes], { type: "application/zip" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "month-end-output.zip";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1000);
    state.saved = true;
    render();
  }

  document.body.addEventListener("click", function (event) {
    var button = event.target.closest("[data-action]");
    if (!button || button.disabled) return;
    var action = button.getAttribute("data-action");
    if (action === "use-sample") useSample();
    else if (action === "pick-file") fileInput.click();
    else if (action === "continue-upload") continueUpload();
    else if (action === "run") runUpdate();
    else if (action === "next") {
      state.step = 4;
      render();
    } else if (action === "download") download();
    else if (action === "back") {
      state.step = Math.max(1, state.step - 1);
      state.error = "";
      render();
    }
  });

  fileInput.addEventListener("change", function () {
    var file = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var rows = pipeline.parseCsv(String(reader.result || ""));
        validateActivity(rows);
        pipeline.checkStatement(rows);
        state.source = "upload";
        state.fileName = file.name;
        state.activity = rows;
        state.error = "";
        state.result = null;
      } catch (err) {
        state.error = file.name + ": " + friendlyError(err);
      }
      render();
    };
    reader.onerror = function () {
      state.error = "This file could not be read.";
      render();
    };
    reader.readAsText(file);
  });

  render();
})();
