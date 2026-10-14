/* Browser port of the transfers, YTD map, and journal passes.
   File text matches the Python CLI for the same fixtures. */
"use strict";

(function (root) {
  var TRANSFER_TYPES = {
    wire: true,
    wire_in: true,
    wire_out: true,
    ach: true,
    ach_in: true,
    ach_out: true,
    contribution: true,
    distribution: true,
    cash_transfer: true,
    security_transfer: true,
    transfer: true,
    margin_paydown: true,
    loan_paydown: true,
    paydown: true,
  };

  var NON_TRANSFER_TYPES = {
    dividend: true,
    interest: true,
    margin_interest: true,
    buy: true,
    sell: true,
    trade: true,
    market_move: true,
    unrealized: true,
    unrealized_gain: true,
    unrealized_loss: true,
    realized_gain: true,
    realized_loss: true,
    fee: true,
    commission: true,
  };

  var KEYWORD_RULES = [
    [/\b(?:margin|loan)\s+paydown\b/i, "margin_paydown"],
    [/\bpaydown\b/i, "margin_paydown"],
    [/\bsecurity transfer\b|\bshare journal\b|\bacats\b/i, "security_transfer"],
    [/\bcash transfer\b|\bcash journal\b/i, "cash_transfer"],
    [/\bcontribution\b/i, "contribution"],
    [/\bdistribution\b/i, "distribution"],
    [/\bwire\b/i, "wire"],
    [/\bach\b/i, "ach"],
    [/\bjournal\b/i, "possible_transfer"],
  ];

  var CATEGORY_ALIASES = {
    wire_in: "wire",
    wire_out: "wire",
    ach_in: "ach",
    ach_out: "ach",
    loan_paydown: "margin_paydown",
    paydown: "margin_paydown",
    transfer: "cash_transfer",
  };

  var LARGE_AMOUNT_THRESHOLD = 100000;
  var LARGE_PLUG_THRESHOLD = 100000;
  var KNOWN_ENTITIES = {
    "Wayne Family Trust": true,
    "Parker Holdings LLC": true,
  };

  var INCOME_GL_MIN = 3000;
  var INCOME_GL_MAX = 3999;
  var BALANCING_GL_CODE = 9999;
  var BALANCING_GL_NAME = "Suspense (review before posting)";
  var JOURNAL_MEMO = "Month-end statement update (demo)";
  var PLUG_MEMO = "Unexplained change: match to transfers list before posting";

  var DUMMY_GL = {
    1200: "Brokerage Cash",
    1210: "Equities",
    1220: "Fixed Income",
    1230: "Other Investments",
    2100: "Margin Loan",
    3100: "Dividend Income",
    3200: "Interest Income",
    3300: "Realized Gain/Loss",
    9999: BALANCING_GL_NAME,
  };

  var SIGN_FLIP_RULE = [
    "SIGN-FLIP RULE (demo only, dummy 3000-series)",
    "=============================================",
    "Brokerage statements typically report dividend, interest, and realized",
    'gain as positive "income received." This demo\'s workpaper uses a',
    "debit-positive convention: income and gain accounts store credit",
    "balances as negative numbers.",
    "",
    "For GL codes 3000-3999 (Dividend Income 3100, Interest Income 3200,",
    "Realized Gain/Loss 3300, and any other demo income/gain account in",
    "that range):",
    "",
    "    mapped_ytd = -statement_amount",
    "",
    "All other dummy GLs keep the statement amount as-is:",
    "",
    "    mapped_ytd = statement_amount",
    "",
    "Missing statement values map to 0. The flip is applied after the",
    "missing-to-zero substitution.",
  ].join("\n");

  var TRANSFER_CSV_FIELDS = [
    "date",
    "entity",
    "account",
    "category",
    "description",
    "amount",
    "security",
    "quantity",
    "counterparty_entity",
    "counterparty_account",
    "flags",
    "record_action",
    "classified_via",
    "balances_updated",
  ];

  var YTD_CSV_FIELDS = [
    "row_order",
    "entity",
    "gl_code",
    "gl_name",
    "prior_ledger",
    "statement_ytd_raw",
    "statement_ytd_mapped",
    "sign_flipped",
    "missing_statement",
    "difference",
    "flags",
  ];

  var JOURNAL_CSV_FIELDS = [
    "line",
    "entity",
    "gl_code",
    "gl_name",
    "debit",
    "credit",
    "memo",
    "flags",
    "is_balancing",
  ];

  var EMAIL_RE = /[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/g;
  var ALLOWED_EMAIL_DOMAINS = { "example.test": true, "example.com": true };
  var UNMASKED_ACCOUNT_RE = /(?<!\*)\d{6,}/;
  var MASKED_ACCOUNT_RE = /^\*{2,}\d{4}$/;
  var SSN_RE = /\b\d{3}-\d{2}-\d{4}\b/;

  function PipelineError(message) {
    var err = new Error(message);
    err.name = "PipelineError";
    return err;
  }

  function cell(row, key) {
    if (!row || row[key] === undefined || row[key] === null) return "";
    return String(row[key]);
  }

  function formatDollars(amount) {
    var sign = amount < 0 ? "-" : "";
    var digits = String(Math.abs(amount));
    var withCommas = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return sign + "$" + withCommas;
  }

  function parseWholeDollars(value, field) {
    field = field || "amount";
    if (value === null || value === undefined) {
      throw PipelineError(field + " is missing; demo requires whole dollars");
    }
    if (typeof value === "boolean") {
      throw PipelineError(field + " must be a whole-dollar amount, not a boolean");
    }
    if (typeof value === "number") {
      if (!Number.isInteger(value)) {
        throw PipelineError(field + " has cents; demo allows round dollars only");
      }
      return value;
    }
    var text = String(value).trim();
    if (text === "") {
      throw PipelineError(field + " is blank; demo requires whole dollars");
    }
    if (/[.]\d*[1-9]/.test(text)) {
      throw PipelineError(field + " has cents; demo allows round dollars only");
    }
    var compact = text.replace(/ /g, "");
    if (compact.charAt(0) === "(" && compact.charAt(compact.length - 1) === ")") {
      compact = "-" + compact.slice(1, -1);
    }
    compact = compact.replace(/\$/g, "").replace(/,/g, "");
    if (compact.endsWith(".0") || compact.endsWith(".00")) {
      compact = compact.slice(0, compact.lastIndexOf("."));
    }
    if (!/^-?\d+$/.test(compact)) {
      throw PipelineError(field + " is not a whole-dollar integer");
    }
    return Number(compact);
  }

  function parseOptionalWholeDollars(value, field) {
    if (value === null || value === undefined) return null;
    if (typeof value === "string" && value.trim() === "") return null;
    return parseWholeDollars(value, field);
  }

  function findEmails(text) {
    var found = [];
    var match;
    EMAIL_RE.lastIndex = 0;
    while ((match = EMAIL_RE.exec(text))) found.push(match[0]);
    return found;
  }

  function emailAllowed(address) {
    var domain = address.split("@").pop().toLowerCase();
    return !!ALLOWED_EMAIL_DOMAINS[domain];
  }

  function assertNoSensitiveText(text, field) {
    if (!text) return;
    var emails = findEmails(text);
    for (var i = 0; i < emails.length; i++) {
      if (!emailAllowed(emails[i])) {
        throw PipelineError(
          field +
            " contains a non-demo email (" +
            emails[i] +
            "); use nobody@example.test or omit emails"
        );
      }
    }
    if (SSN_RE.test(text)) {
      throw PipelineError(field + " looks like a taxpayer ID; strip it");
    }
    if (UNMASKED_ACCOUNT_RE.test(text)) {
      throw PipelineError(
        field + " contains an unmasked number run; use ****1234-style masks"
      );
    }
  }

  function assertMaskedAccount(value, field) {
    var text = String(value || "").trim();
    if (!text) {
      throw PipelineError(field + " is required and must look like ****1234");
    }
    if (!MASKED_ACCOUNT_RE.test(text)) {
      throw PipelineError(field + " must be a masked account (****1234 style)");
    }
    return text;
  }

  function parseDummyGl(value, field) {
    field = field || "gl_code";
    if (value === null || value === undefined || (typeof value === "string" && value.trim() === "")) {
      throw PipelineError(field + " is required");
    }
    var text = String(value).trim();
    if (!/^-?\d+$/.test(text)) {
      throw PipelineError(field + " is not a dummy GL code");
    }
    var code = Number(text);
    if (!Object.prototype.hasOwnProperty.call(DUMMY_GL, code)) {
      throw PipelineError(field + "=" + code + " is not in the dummy catalog");
    }
    return code;
  }

  function scrubRecord(record, fields) {
    for (var i = 0; i < fields.length; i++) {
      var value = record[fields[i]];
      if (value === null || value === undefined) continue;
      assertNoSensitiveText(String(value), fields[i]);
    }
  }

  function collectScrubIssues(text, field) {
    var issues = [];
    if (!text) return issues;
    var emails = findEmails(text);
    for (var i = 0; i < emails.length; i++) {
      if (!emailAllowed(emails[i])) issues.push(field + ":non_demo_email");
    }
    if (SSN_RE.test(text)) issues.push(field + ":taxpayer_id");
    if (UNMASKED_ACCOUNT_RE.test(text)) issues.push(field + ":unmasked_number");
    return issues;
  }

  function categoryFromDescription(description) {
    if (!description) return null;
    for (var i = 0; i < KEYWORD_RULES.length; i++) {
      if (KEYWORD_RULES[i][0].test(description)) return KEYWORD_RULES[i][1];
    }
    return null;
  }

  function scrubActivity(row) {
    var fields = ["entity", "description", "security", "counterparty_entity", "activity_type", "date"];
    for (var i = 0; i < fields.length; i++) {
      var value = cell(row, fields[i]);
      if (value) assertNoSensitiveText(value, fields[i]);
    }
    var account = cell(row, "account").trim();
    if (account) assertMaskedAccount(account, "account");
    var counter = cell(row, "counterparty_account").trim();
    if (counter) assertMaskedAccount(counter, "counterparty_account");
    parseWholeDollars(row.amount, "amount");
  }

  function classifyRow(row) {
    var activityType = cell(row, "activity_type").trim().toLowerCase();
    var description = cell(row, "description").trim();
    var classifiedVia = "activity_type";
    var category = activityType;
    var flags = [];

    if (NON_TRANSFER_TYPES[activityType]) return null;
    if (TRANSFER_TYPES[activityType]) {
      category = CATEGORY_ALIASES[activityType] || activityType;
    } else if (activityType === "" || activityType === "unknown" || activityType === "other") {
      var keywordCategory = categoryFromDescription(description);
      if (keywordCategory === null) return null;
      category = keywordCategory;
      classifiedVia = "description_keyword";
      if (keywordCategory === "possible_transfer") flags.push("AMBIGUOUS_TYPE");
    } else {
      throw PipelineError("activity_type=" + JSON.stringify(activityType) + " is not a known demo type");
    }

    var amount = parseWholeDollars(row.amount, "amount");
    var entity = cell(row, "entity").trim();
    var counterpartyEntity = cell(row, "counterparty_entity").trim();
    var counterpartyAccount = cell(row, "counterparty_account").trim();
    var security = cell(row, "security").trim();
    var quantity = cell(row, "quantity").trim();

    if (Math.abs(amount) >= LARGE_AMOUNT_THRESHOLD) flags.push("LARGE_AMOUNT");
    if (
      counterpartyEntity &&
      entity &&
      counterpartyEntity !== entity &&
      KNOWN_ENTITIES[counterpartyEntity] &&
      KNOWN_ENTITIES[entity]
    ) {
      flags.push("INTER_ENTITY");
    }
    if (
      category === "wire" ||
      category === "wire_in" ||
      category === "wire_out" ||
      category === "ach" ||
      category === "contribution" ||
      category === "distribution"
    ) {
      if (!counterpartyEntity && !counterpartyAccount) flags.push("MISSING_COUNTERPARTY");
    }
    if (category === "security_transfer" && !quantity) flags.push("SECURITY_WITHOUT_QTY");
    if (classifiedVia === "description_keyword") flags.push("KEYWORD_CLASSIFIED");

    var extras = collectScrubIssues(description, "description");
    for (var i = 0; i < extras.length; i++) flags.push(extras[i].toUpperCase());
    var recordAction = flags.length ? "REVIEW" : "RECORD";
    if (flags.length) flags.push("NEEDS_HUMAN_REVIEW");

    return {
      date: cell(row, "date").trim(),
      entity: entity,
      account: cell(row, "account").trim(),
      category: category,
      description: description,
      amount: amount,
      security: security,
      quantity: quantity,
      counterparty_entity: counterpartyEntity,
      counterparty_account: counterpartyAccount,
      flags: flags,
      record_action: recordAction,
      source_activity_type: activityType,
      classified_via: classifiedVia,
      balances_updated: false,
    };
  }

  function classifyTransfers(activities) {
    var lines = [];
    var skipped = 0;
    for (var i = 0; i < activities.length; i++) {
      scrubActivity(activities[i]);
      var decision = classifyRow(activities[i]);
      if (decision === null) skipped += 1;
      else lines.push(decision);
    }
    return { lines: lines, skippedOrdinary: skipped, balancesUpdated: false };
  }

  function transferRow(line) {
    return {
      date: line.date,
      entity: line.entity,
      account: line.account,
      category: line.category,
      description: line.description,
      amount: line.amount,
      security: line.security,
      quantity: line.quantity,
      counterparty_entity: line.counterparty_entity,
      counterparty_account: line.counterparty_account,
      flags: line.flags.join("|"),
      record_action: line.record_action,
      source_activity_type: line.source_activity_type,
      classified_via: line.classified_via,
      balances_updated: "false",
    };
  }

  function isIncome(glCode) {
    return glCode >= INCOME_GL_MIN && glCode <= INCOME_GL_MAX;
  }

  function statementCell(row) {
    var keys = ["statement_ytd", "statement_ytd_raw", "ytd", "statement"];
    for (var i = 0; i < keys.length; i++) {
      if (row && Object.prototype.hasOwnProperty.call(row, keys[i])) return row[keys[i]];
    }
    return null;
  }

  function coerceStatementList(statementValues) {
    if (statementValues === null || statementValues === undefined) return null;
    var values = [];
    for (var i = 0; i < statementValues.length; i++) {
      var item = statementValues[i];
      if (item && typeof item === "object" && !Array.isArray(item)) values.push(statementCell(item));
      else values.push(item);
    }
    return values;
  }

  function rowOrder(ledger, index) {
    var raw = ledger.row_order;
    if (raw === null || raw === undefined || String(raw).trim() === "") return index + 1;
    var text = String(raw).trim();
    if (!/^-?\d+$/.test(text)) throw PipelineError("row_order is not an integer");
    return Number(text);
  }

  function mapYtdColumn(ledgerRows, statementValues) {
    var resultFlags = [];
    var rows = [];
    var rawValues = coerceStatementList(statementValues);
    if (rawValues !== null && rawValues.length !== ledgerRows.length) {
      resultFlags.push(
        "ROW_COUNT_MISMATCH:ledger=" + ledgerRows.length + ",statement=" + rawValues.length
      );
    }
    for (var index = 0; index < ledgerRows.length; index++) {
      var ledger = ledgerRows[index];
      scrubRecord(ledger, ["entity", "gl_name"]);
      var glCode = parseDummyGl(ledger.gl_code);
      var name = cell(ledger, "gl_name").trim() || DUMMY_GL[glCode] || "Unknown dummy GL " + glCode;
      var prior = parseWholeDollars(ledger.prior_ledger, "prior_ledger");
      var order = rowOrder(ledger, index);
      var missing = false;
      var parsed;
      if (rawValues !== null) {
        if (index < rawValues.length) parsed = parseOptionalWholeDollars(rawValues[index], "statement_ytd");
        else {
          parsed = null;
          missing = true;
        }
      } else {
        parsed = parseOptionalWholeDollars(statementCell(ledger), "statement_ytd");
      }
      var rawAmount;
      if (parsed === null) {
        missing = true;
        rawAmount = 0;
      } else {
        rawAmount = parsed;
      }
      var mapped = isIncome(glCode) ? -rawAmount : rawAmount;
      var flipped = isIncome(glCode);
      var flags = [];
      if (missing) {
        flags.push("MISSING_STATEMENT_VALUE");
        resultFlags.push("MISSING_STATEMENT_VALUE:row=" + order);
      }
      if (flipped && mapped > 0) {
        flags.push("INCOME_SIGN_UNEXPECTED");
        resultFlags.push("INCOME_SIGN_UNEXPECTED:row=" + order);
      }
      if (flipped && prior > 0) {
        flags.push("PRIOR_INCOME_NOT_CREDIT");
        resultFlags.push("PRIOR_INCOME_NOT_CREDIT:row=" + order);
      }
      rows.push({
        row_order: order,
        entity: cell(ledger, "entity").trim(),
        gl_code: glCode,
        gl_name: name,
        prior_ledger: prior,
        statement_ytd_raw: rawAmount,
        statement_ytd_mapped: mapped,
        sign_flipped: flipped,
        missing_statement: missing,
        flags: flags,
        difference: mapped - prior,
      });
    }
    if (rawValues !== null && rawValues.length > ledgerRows.length) {
      resultFlags.push("EXTRA_STATEMENT_ROWS_DROPPED:" + (rawValues.length - ledgerRows.length));
    }
    return { rows: rows, flags: resultFlags, signFlipRule: SIGN_FLIP_RULE };
  }

  function ytdRow(row) {
    return {
      row_order: row.row_order,
      entity: row.entity,
      gl_code: row.gl_code,
      gl_name: row.gl_name,
      prior_ledger: row.prior_ledger,
      statement_ytd_raw: row.statement_ytd_raw,
      statement_ytd_mapped: row.statement_ytd_mapped,
      sign_flipped: row.sign_flipped ? "yes" : "no",
      missing_statement: row.missing_statement ? "yes" : "no",
      difference: row.difference,
      flags: row.flags.join("|"),
    };
  }

  function splitDebitCredit(difference) {
    if (difference > 0) return [difference, 0];
    if (difference < 0) return [0, -difference];
    return [0, 0];
  }

  function buildJournal(mappedRows) {
    var lines = [];
    var flags = [];
    var lineNo = 1;
    for (var i = 0; i < mappedRows.length; i++) {
      var row = mappedRows[i];
      var sides = splitDebitCredit(row.difference);
      if (sides[0] === 0 && sides[1] === 0) continue;
      lines.push({
        line: lineNo,
        entity: row.entity,
        gl_code: row.gl_code,
        gl_name: row.gl_name,
        debit: sides[0],
        credit: sides[1],
        memo: JOURNAL_MEMO,
        flags: row.flags.slice(),
        is_balancing: false,
      });
      lineNo += 1;
    }
    var entities = [];
    var seen = {};
    for (var j = 0; j < lines.length; j++) {
      if (!seen[lines[j].entity]) {
        seen[lines[j].entity] = true;
        entities.push(lines[j].entity);
      }
    }
    var plugAmount = 0;
    for (var e = 0; e < entities.length; e++) {
      var entity = entities[e];
      var entityLines = [];
      for (var k = 0; k < lines.length; k++) {
        if (lines[k].entity === entity && !lines[k].is_balancing) entityLines.push(lines[k]);
      }
      var debits = 0;
      var credits = 0;
      for (var n = 0; n < entityLines.length; n++) {
        debits += entityLines[n].debit;
        credits += entityLines[n].credit;
      }
      var plug = debits - credits;
      if (plug === 0) continue;
      var lineFlags = ["UNBALANCED_BEFORE_PLUG"];
      if (Math.abs(plug) >= LARGE_PLUG_THRESHOLD) lineFlags.push("LARGE_PLUG");
      for (var f = 0; f < lineFlags.length; f++) {
        if (flags.indexOf(lineFlags[f]) === -1) flags.push(lineFlags[f]);
      }
      plugAmount += Math.abs(plug);
      var plugDebit = plug > 0 ? 0 : -plug;
      var plugCredit = plug > 0 ? plug : 0;
      lines.push({
        line: lineNo,
        entity: entity,
        gl_code: BALANCING_GL_CODE,
        gl_name: BALANCING_GL_NAME,
        debit: plugDebit,
        credit: plugCredit,
        memo: PLUG_MEMO,
        flags: lineFlags,
        is_balancing: true,
      });
      lineNo += 1;
    }
    var totalDebit = 0;
    var totalCredit = 0;
    for (var t = 0; t < lines.length; t++) {
      totalDebit += lines[t].debit;
      totalCredit += lines[t].credit;
    }
    if (totalDebit !== totalCredit) throw PipelineError("journal construction failed to balance");
    return {
      lines: lines,
      flags: flags,
      totalDebit: totalDebit,
      totalCredit: totalCredit,
      plugAmount: plugAmount,
      isBalanced: true,
    };
  }

  function journalRow(line) {
    return {
      line: line.line,
      entity: line.entity,
      gl_code: line.gl_code,
      gl_name: line.gl_name,
      debit: line.debit,
      credit: line.credit,
      memo: line.memo,
      flags: line.flags.join("|"),
      is_balancing: line.is_balancing ? "yes" : "no",
    };
  }

  function csvEscape(value) {
    var text = value === null || value === undefined ? "" : String(value);
    if (/[",\r\n]/.test(text)) return '"' + text.replace(/"/g, '""') + '"';
    return text;
  }

  function writeCsv(rows, fields) {
    var lines = [fields.map(csvEscape).join(",")];
    for (var i = 0; i < rows.length; i++) {
      var cells = [];
      for (var c = 0; c < fields.length; c++) cells.push(csvEscape(rows[i][fields[c]]));
      lines.push(cells.join(","));
    }
    return lines.join("\r\n") + "\r\n";
  }

  function writeJson(value) {
    return (
      JSON.stringify(value, null, 2).replace(/[\u007f-\uffff]/g, function (ch) {
        return "\\u" + ch.charCodeAt(0).toString(16).padStart(4, "0");
      }) + "\n"
    );
  }

  function summaryMarkdown(transfers, ytd, journal) {
    var transferLines = transfers.lines
      .map(function (line) {
        return (
          "- " +
          line.date +
          " | " +
          line.entity +
          " | " +
          line.category +
          " | " +
          formatDollars(line.amount) +
          " | " +
          line.record_action +
          " | " +
          (line.flags.join("|") || "-")
        );
      })
      .join("\n");
    var ytdLines = ytd.rows
      .map(function (row) {
        return (
          "- " +
          row.row_order +
          ". " +
          row.entity +
          " " +
          row.gl_code +
          " " +
          row.gl_name +
          ": raw " +
          formatDollars(row.statement_ytd_raw) +
          " -> mapped " +
          formatDollars(row.statement_ytd_mapped) +
          (row.sign_flipped ? " (sign-flip)" : "") +
          (row.missing_statement ? " [missing->0]" : "")
        );
      })
      .join("\n");
    var journalLines = journal.lines
      .map(function (line) {
        return (
          "- " +
          line.line +
          ". " +
          line.gl_code +
          " " +
          line.gl_name +
          ": Dr " +
          formatDollars(line.debit) +
          " / Cr " +
          formatDollars(line.credit) +
          (line.is_balancing ? "  \u00e2\u2020\u0090 balancing" : "")
        );
      })
      .join("\n");
    return (
      "# Month-end run summary (synthetic demo)\n" +
      "\n" +
      "Transfers pass did **not** update balances.\n" +
      "\n" +
      "## Transfers to record\n" +
      "\n" +
      (transferLines || "- (none)") +
      "\n" +
      "\n" +
      "Ordinary (non-transfer) activity skipped: " +
      transfers.skippedOrdinary +
      "\n" +
      "\n" +
      "## YTD paste column (row-aligned)\n" +
      "\n" +
      ytdLines +
      "\n" +
      "\n" +
      "YTD flags: " +
      (ytd.flags.length ? ytd.flags.join(", ") : "none") +
      "\n" +
      "\n" +
      "## Sign-flip rule\n" +
      "\n" +
      SIGN_FLIP_RULE +
      "\n" +
      "\n" +
      "## Journal\n" +
      "\n" +
      "Balanced: **" +
      (journal.isBalanced ? "True" : "False") +
      "**\n" +
      "Debits " +
      formatDollars(journal.totalDebit) +
      " = Credits " +
      formatDollars(journal.totalCredit) +
      "\n" +
      "Suspense " +
      formatDollars(journal.plugAmount) +
      "\n" +
      "\n" +
      journalLines +
      "\n"
    );
  }

  function buildOutputFiles(activities, ledgerRows, statementRows) {
    var transfers = classifyTransfers(activities);
    var ytd = mapYtdColumn(ledgerRows, statementRows);
    var journal = buildJournal(ytd.rows);
    var transferRows = transfers.lines.map(transferRow);
    var mappedRows = ytd.rows.map(ytdRow);
    var journalRows = journal.lines.map(journalRow);
    var reviewCount = 0;
    for (var i = 0; i < transfers.lines.length; i++) {
      if (transfers.lines[i].record_action === "REVIEW") reviewCount += 1;
    }
    var paste = ytd.rows.map(function (row) {
      return row.statement_ytd_mapped;
    });
    var files = {
      "transfers.csv": writeCsv(transferRows, TRANSFER_CSV_FIELDS),
      "transfers.json": writeJson({
        balances_updated: false,
        note: "Transfers pass does not update ledger balances.",
        to_record_count: transfers.lines.length,
        skipped_ordinary_count: transfers.skippedOrdinary,
        review_count: reviewCount,
        lines: transferRows,
      }),
      "ytd_map.csv": writeCsv(mappedRows, YTD_CSV_FIELDS),
      "ytd_map.json": writeJson({
        sign_flip_rule: ytd.signFlipRule,
        row_count: ytd.rows.length,
        flags: ytd.flags.slice(),
        paste_column: paste,
        rows: mappedRows,
      }),
      "ytd_paste_column.txt": paste.join("\n") + "\n",
      "ytd_paste_column.csv": writeCsv(
        paste.map(function (value) {
          return { statement_ytd_mapped: value };
        }),
        ["statement_ytd_mapped"]
      ),
      "journal.csv": writeCsv(journalRows, JOURNAL_CSV_FIELDS),
      "journal.json": writeJson({
        balanced: journal.isBalanced,
        total_debit: journal.totalDebit,
        total_credit: journal.totalCredit,
        plug_amount: journal.plugAmount,
        flags: journal.flags.slice(),
        lines: journalRows,
      }),
      "run_summary.json": writeJson({
        synthetic_only: true,
        balances_updated_in_transfers_pass: false,
        transfers_to_record: transfers.lines.length,
        transfers_review: reviewCount,
        ordinary_activity_skipped: transfers.skippedOrdinary,
        ytd_rows: ytd.rows.length,
        ytd_flags: ytd.flags.slice(),
        journal_balanced: journal.isBalanced,
        journal_total_debit: journal.totalDebit,
        journal_total_credit: journal.totalCredit,
        journal_plug: journal.plugAmount,
        journal_flags: journal.flags.slice(),
      }),
      "run_summary.md": summaryMarkdown(transfers, ytd, journal),
    };
    return { transfers: transfers, ytd: ytd, journal: journal, files: files };
  }

  function parseCsv(text) {
    if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
    var rows = [];
    var row = [];
    var field = "";
    var inQuotes = false;
    for (var i = 0; i < text.length; i++) {
      var ch = text.charAt(i);
      if (inQuotes) {
        if (ch === '"') {
          if (text.charAt(i + 1) === '"') {
            field += '"';
            i += 1;
          } else {
            inQuotes = false;
          }
        } else {
          field += ch;
        }
        continue;
      }
      if (ch === '"') {
        inQuotes = true;
        continue;
      }
      if (ch === ",") {
        row.push(field);
        field = "";
        continue;
      }
      if (ch === "\r") {
        row.push(field);
        rows.push(row);
        row = [];
        field = "";
        if (text.charAt(i + 1) === "\n") i += 1;
        continue;
      }
      if (ch === "\n") {
        row.push(field);
        rows.push(row);
        row = [];
        field = "";
        continue;
      }
      field += ch;
    }
    if (field.length || row.length) {
      row.push(field);
      rows.push(row);
    }
    if (!rows.length) return [];
    var headers = rows[0];
    var out = [];
    for (var r = 1; r < rows.length; r++) {
      var cells = rows[r];
      if (cells.length === 1 && cells[0] === "") continue;
      var obj = {};
      for (var c = 0; c < headers.length; c++) {
        if (!headers[c]) continue;
        obj[headers[c]] = cells[c] === undefined ? "" : cells[c];
      }
      out.push(obj);
    }
    return out;
  }

  function crc32(bytes) {
    var table = crc32.table;
    if (!table) {
      table = new Uint32Array(256);
      for (var n = 0; n < 256; n++) {
        var c = n;
        for (var k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        table[n] = c >>> 0;
      }
      crc32.table = table;
    }
    var crc = 0xffffffff;
    for (var i = 0; i < bytes.length; i++) crc = table[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  }

  function createZip(files) {
    var encoder = new TextEncoder();
    var names = Object.keys(files);
    var parts = [];
    var central = [];
    var offset = 0;
    var dosDate = ((2026 - 1980) << 9) | (8 << 5) | 31;
    for (var i = 0; i < names.length; i++) {
      var nameBytes = encoder.encode(names[i]);
      var data = typeof files[names[i]] === "string" ? encoder.encode(files[names[i]]) : files[names[i]];
      var crc = crc32(data);
      var local = new Uint8Array(30 + nameBytes.length);
      var view = new DataView(local.buffer);
      view.setUint32(0, 0x04034b50, true);
      view.setUint16(4, 20, true);
      view.setUint16(6, 0, true);
      view.setUint16(8, 0, true);
      view.setUint16(10, 0, true);
      view.setUint16(12, dosDate, true);
      view.setUint32(14, crc, true);
      view.setUint32(18, data.length, true);
      view.setUint32(22, data.length, true);
      view.setUint16(26, nameBytes.length, true);
      view.setUint16(28, 0, true);
      local.set(nameBytes, 30);
      parts.push(local, data);
      var cen = new Uint8Array(46 + nameBytes.length);
      var cv = new DataView(cen.buffer);
      cv.setUint32(0, 0x02014b50, true);
      cv.setUint16(4, 20, true);
      cv.setUint16(6, 20, true);
      cv.setUint16(8, 0, true);
      cv.setUint16(10, 0, true);
      cv.setUint16(12, 0, true);
      cv.setUint16(14, dosDate, true);
      cv.setUint32(16, crc, true);
      cv.setUint32(20, data.length, true);
      cv.setUint32(24, data.length, true);
      cv.setUint16(28, nameBytes.length, true);
      cv.setUint16(30, 0, true);
      cv.setUint16(32, 0, true);
      cv.setUint16(34, 0, true);
      cv.setUint16(36, 0, true);
      cv.setUint32(38, 0, true);
      cv.setUint32(42, offset, true);
      cen.set(nameBytes, 46);
      central.push(cen);
      offset += local.length + data.length;
    }
    var centralSize = 0;
    for (var j = 0; j < central.length; j++) centralSize += central[j].length;
    var end = new Uint8Array(22);
    var ev = new DataView(end.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(4, 0, true);
    ev.setUint16(6, 0, true);
    ev.setUint16(8, names.length, true);
    ev.setUint16(10, names.length, true);
    ev.setUint32(12, centralSize, true);
    ev.setUint32(16, offset, true);
    ev.setUint16(20, 0, true);
    var chunks = parts.concat(central, [end]);
    var total = 0;
    for (var p = 0; p < chunks.length; p++) total += chunks[p].length;
    var out = new Uint8Array(total);
    var cursor = 0;
    for (var q = 0; q < chunks.length; q++) {
      out.set(chunks[q], cursor);
      cursor += chunks[q].length;
    }
    return out;
  }

  var api = {
    PipelineError: PipelineError,
    SIGN_FLIP_RULE: SIGN_FLIP_RULE,
    formatDollars: formatDollars,
    parseCsv: parseCsv,
    checkStatement: classifyTransfers,
    buildOutputFiles: buildOutputFiles,
    createZip: createZip,
    OUTPUT_NAMES: [
      "transfers.csv",
      "transfers.json",
      "ytd_map.csv",
      "ytd_map.json",
      "ytd_paste_column.txt",
      "ytd_paste_column.csv",
      "journal.csv",
      "journal.json",
      "run_summary.json",
      "run_summary.md",
    ],
  };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.BrokeragePipeline = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
