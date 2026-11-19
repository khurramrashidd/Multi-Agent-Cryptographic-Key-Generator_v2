// Builds the ICCCT 2027 Springer LNNS manuscript for CryptoKMS.
// Usage: node build_paper.js vals.json figs_dir out.docx
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  AlignmentType, WidthType, BorderStyle, LevelFormat, ExternalHyperlink, VerticalAlign,
} = require("docx");

const V = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const FIG = process.argv[3];
const OUT = process.argv[4];

const FONT = "Times New Roman";
const MONO = "Courier New";
const TEXT_W = 6917;            // 12.2 cm text block (DXA)
const BODY = 20, SMALL = 18;    // half-points: 10 pt, 9 pt
const INDENT = 284;             // 0.5 cm first-line indent

// ---------- inline markup: **bold**, *italic*, _{sub}, ^{sup} ----------
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|_\{[^}]+\}|\^\{[^}]+\})/g;
  let last = 0, m;
  const mk = (t, extra = {}) => new TextRun({ text: t, font: FONT, size: BODY, ...base, ...extra });
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(mk(text.slice(last, m.index)));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(...runs(tok.slice(2, -2), { ...base, bold: true }));
    else if (tok.startsWith("*")) out.push(...runs(tok.slice(1, -1), { ...base, italics: true }));
    else if (tok.startsWith("_{")) out.push(mk(tok.slice(2, -1), { subScript: true }));
    else out.push(mk(tok.slice(2, -1), { superScript: true }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(mk(text.slice(last)));
  return out;
}

let afterHeading = true;
function P(text, opts = {}) {
  const first = afterHeading || opts.first;
  afterHeading = false;
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 0, after: 0, line: 240 },
    indent: first ? undefined : { firstLine: INDENT },
    children: runs(text),
  });
}
function H1(num, text) {
  afterHeading = true;
  return new Paragraph({
    keepNext: true, keepLines: true,
    spacing: { before: 300, after: 150 },
    children: [new TextRun({ text: `${num} ${text}`, font: FONT, size: 24, bold: true })],
  });
}
function H2(num, text) {
  afterHeading = true;
  return new Paragraph({
    keepNext: true, keepLines: true,
    spacing: { before: 180, after: 100 },
    children: [new TextRun({ text: `${num} ${text}`, font: FONT, size: BODY, bold: true })],
  });
}
function caption(label, text, isTable) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    keepNext: !!isTable,
    spacing: isTable ? { before: 200, after: 100 } : { before: 80, after: 220 },
    children: [
      new TextRun({ text: `${label} `, font: FONT, size: SMALL, bold: true }),
      ...runs(text, { size: SMALL }),
    ],
  });
}
function figure(file, wPx, hPxSrc, wSrc, label, text) {
  const h = Math.round(wPx * hPxSrc / wSrc);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 200, after: 0 },
      children: [new ImageRun({
        type: "png", data: fs.readFileSync(path.join(FIG, file)),
        transformation: { width: wPx, height: h },
        altText: { title: label, description: text, name: file },
      })],
    }),
    caption(label, text, false),
  ];
}

// ---------- booktabs-style tables (rules only at top, under header, bottom) ----------
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const RULE = (sz) => ({ style: BorderStyle.SINGLE, size: sz, color: "000000" });
function cell(text, width, { bold = false, align = AlignmentType.CENTER, top, bottom, keep = true } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    margins: { top: 30, bottom: 30, left: 60, right: 60 },
    borders: { top: top || NONE, bottom: bottom || NONE, left: NONE, right: NONE },
    children: [new Paragraph({
      alignment: align, spacing: { before: 0, after: 0, line: 220 }, keepNext: keep, keepLines: true,
      children: runs(text, { size: SMALL, bold }),
    })],
  });
}
function table(headers, rows, widths, { firstLeft = true } = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const hdr = new TableRow({
    tableHeader: true, cantSplit: true,
    children: headers.map((h, i) => cell(h, widths[i], {
      bold: true, align: (i === 0 && firstLeft) ? AlignmentType.LEFT : AlignmentType.CENTER,
      top: RULE(8), bottom: RULE(4),
    })),
  });
  const body = rows.map((r, ri) => new TableRow({
    cantSplit: true,
    children: r.map((c, i) => cell(c, widths[i], {
      align: (i === 0 && firstLeft) ? AlignmentType.LEFT : AlignmentType.CENTER,
      bottom: ri === rows.length - 1 ? RULE(8) : undefined,
      keep: ri < rows.length - 1,
    })),
  }));
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    alignment: AlignmentType.CENTER,
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: [hdr, ...body],
  });
}
const fixSub = (s) => s.replace(/H_L/g, "H_{L}").replace(/2\^15/g, "2^{15}");

// ---------- algorithm box ----------
function algorithm(lines) {
  const out = [new Paragraph({
    keepNext: true, spacing: { before: 200, after: 60 },
    border: { top: RULE(8) },
    children: [new TextRun({ text: "Algorithm 1. ", font: FONT, size: SMALL, bold: true }),
      new TextRun({ text: "Fail-closed issuance loop with unanimous acceptance", font: FONT, size: SMALL })],
  })];
  lines.forEach((l, i) => out.push(new Paragraph({
    keepNext: i < lines.length - 1, keepLines: true,
    spacing: { before: 0, after: 0, line: 220 },
    border: i === lines.length - 1 ? { bottom: RULE(8) } : undefined,
    children: [new TextRun({ text: l.replace(/ /g, " "), font: MONO, size: 15 })],
  })));
  out.push(new Paragraph({ spacing: { before: 0, after: 120 }, children: [] }));
  return out;
}

// ---------- front matter ----------
const front = [
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 0, after: 240, line: 300 },
    children: [new TextRun({
      text: "CryptoKMS: A Multi-Agent Validate-Before-Dispatch Framework for Fault-Aware Cryptographic Key Issuance in Secure Communication Systems",
      font: FONT, size: 28, bold: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 0, after: 120 },
    children: runs("Khurram Rashid^{(✉)}, Sarang M. Patil, Kinza Zahra, Prapti Patil, and Shreya Deshpande"),
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 0, after: 40 },
    children: runs("Department of Computer Science and Engineering, Amity School of Engineering and Technology, Amity University Mumbai, Maharashtra, India", { size: SMALL }),
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 0, after: 360 },
    children: runs("khurramrashid0786@gmail.com, smpatil@mum.amity.edu, kinzazahra0786@gmail.com, praptipatil5003@gmail.com, deshpandeshreyas05@gmail.com", { size: SMALL }),
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED, indent: { left: 567, right: 567 },
    spacing: { before: 0, after: 120, line: 220 },
    children: [
      new TextRun({ text: "Abstract. ", font: FONT, size: SMALL, bold: true }),
      ...runs("Secure communication systems inherit their strength from the keys they issue, yet deployed generators give no continuous evidence that they still behave correctly. This paper presents CryptoKMS, a multi-agent key management service that replaces generate-and-trust with validate-before-dispatch: specialised agents generate AES, ECC and RSA keys and screen the raw material of every candidate with a Shannon-entropy test, the NIST SP 800-22 Monobit test, a bit-transition statistic and a duplicate index inside a fail-closed loop, attaching a verdict trail to every dispatched key. Evaluating 11,200 baseline and 10,000 fault-injected keys, we report three transferable findings. First, entropy thresholds referenced to the theoretical ceiling are unsafe: a 90% rule on the log_{2} L ceiling rejects 69% of genuine RSA-2048 moduli, while a threshold at the 0.1% quantile of the entropy of L uniform bytes raises RSA-2048 acceptance from 31.0% to 96.5%. Second, testing PEM or DER encodings instead of raw key material drives Monobit pass rates from 98.8% to 0.0%. Third, a sequential binomial alarm flags a source with P(1) = 0.55 after a median of 21 keys and a stuck-at fault after 2, with no false alarm in 300 healthy streams, but cannot distinguish a seeded Mersenne Twister from a CSPRNG. Validation costs 0.03\u20130.07 ms per key.", { size: SMALL }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.LEFT, indent: { left: 567, right: 567 },
    spacing: { before: 0, after: 240, line: 220 },
    children: [
      new TextRun({ text: "Keywords: ", font: FONT, size: SMALL, bold: true }),
      new TextRun({ text: "Cryptographic key management · Multi-agent systems · Entropy validation · NIST SP 800-22 · Fault injection · Secure communication", font: FONT, size: SMALL }),
    ],
  }),
];

// ---------- body ----------
const B = [];
B.push(H1("1", "Introduction"));
B.push(P(`Secure communication systems inherit their strength from the keys they issue. TLS sessions, encrypted channels, signed updates and API credentials all depend on keys for confidentiality, integrity and authentication [1], and every key is only as strong as the randomness available when it was generated [2]. Generation is frequently the weakest link. The 2008 Debian OpenSSL defect reduced the effective seed space to 15 bits and silently exposed SSH and TLS servers for almost two years [3]; an Internet-wide survey traced tens of thousands of factorable RSA moduli on network devices to malfunctioning generators [4]; and the Dual_EC_DRBG episode showed that even standardised generators warrant independent scrutiny [5].`));
B.push(P(`What unites these failures is the absence of feedback. Mainstream libraries follow a *generate-and-trust* paradigm [6, 7]: a key is emitted from whatever entropy is available, and the caller cannot tell a healthy generator from a broken one. Certification examines a design once; nothing re-examines the running instance that issues each key.`));
B.push(P(`This paper presents CryptoKMS, a multi-agent key management service built on the opposite principle, *validate-before-dispatch*: every candidate key is screened by specialised agents before release, every verdict is attached to the dispatched key, and issuance fails closed when validation cannot be satisfied. Here *multi-agent* denotes the decomposition of the issuance path into independent, auditable components; the acceptance rule itself is deliberately deterministic, so every decision is reproducible.`));
B.push(P(`The contributions are fourfold: (i) a validate-before-dispatch architecture that works with any generator and emits per-key evidence (Sect. 3); (ii) a corrected entropy reference, showing that a 90% rule on the log_{2} *L* ceiling rejects 69% of genuine RSA-2048 moduli and that a threshold calibrated to the entropy of *L* uniform bytes restores acceptance to 96.5% (Sect. 5.2); (iii) an encoding artefact that drives Monobit pass rates from 98.8% to 0.0% when PEM or DER exports are tested instead of raw material (Sect. 5.3); and (iv) a fault-injection characterisation, with a sequential alarm and a bias sweep, of which failures issuance-time validation detects, how quickly, and which it cannot (Sects. 5.4\u20135.5). Sections 2\u20136 present the literature review, methodology, experimental work, result analysis and conclusions.`));

B.push(H1("2", "Literature Review"));
B.push(H2("2.1", "Randomness Standards and Continuous Testing"));
B.push(P(`NIST SP 800-90A specifies deterministic random bit generators [8], SP 800-90B adds validation and continuous health tests for entropy sources [9], and SP 800-90C, finalised in 2025, composes both into complete constructions [10]. SP 800-22 supplies the statistical test battery, including the Monobit test used here, and cautions that statistical testing cannot substitute for cryptanalysis [11]; SP 800-57 gives the security-strength equivalences used to classify keys [12]. Health tests are closest in spirit to this work, but they run at the entropy source, whereas CryptoKMS sits at the application boundary, where encodings, libraries and misconfiguration intervene.`));
B.push(H2("2.2", "Generator Failures in Deployed Systems"));
B.push(P(`The Debian incident [3] and the weak-key survey of Heninger et al. [4] both arose in deployments of sound, standardised algorithms: the defect lay in how a running instance was seeded. Corrigan-Gibbs et al. propose an entropy authority that contributes and certifies randomness through a protocol [2], which strengthens generation but requires protocol changes on both sides. CryptoKMS is complementary: it changes nothing about generation and inspects what a generator actually produced before the key leaves the service.`));
B.push(H2("2.3", "Learned and AI-Assisted Generators"));
B.push(P(`A separate line of work trains neural networks to produce pseudo-randomness. De Bernardi et al. train a generator adversarially against a predictor and report roughly 98\u201399% NIST pass rates [13]; Kim et al. add recurrent layers and deploy on an embedded accelerator [14]; Oak et al. present GAN-based candidates at a security venue [15]; and EPRNG trains a deep convolutional GAN on vehicle imagery with an entropy-driven stopping rule [16]. These approaches improve or replace the generator, and their acceptance behaviour is implicit in an opaque model. CryptoKMS takes the opposite design point: the generator remains a vetted operating-system CSPRNG, and the contribution is an auditable validation layer around issuance, behind which a learned generator could also sit unchanged.`));
B.push(H2("2.4", "Key Management in Practice"));
B.push(P(`Key handling is a further attack surface. Cryptographic failures rank among the most prevalent web-application risks [17], cloud providers publish standing rotation guidance because credential exposure recurs [18], the Capital One breach traced mass exfiltration to a misconfigured credential path [19], and Heartbleed showed private keys leaking from process memory [20]. These cases motivate the vault policies of Sect. 3.6.`));
B.push(H2("2.5", "Research Gap"));
B.push(P(`Table 1 positions the approaches. No learned generator validates keys at issuance or produces per-key evidence, and source-level health tests do not observe what reaches the application. The gap addressed here is continuous, per-key, auditable evidence that the instance issuing keys still behaves correctly.`));
B.push(caption("Table 1.", "Positioning of CryptoKMS against existing approaches.", true));
B.push(table(
  ["Approach", "Role of AI", "Validates at issuance", "Per-key evidence", "Detects deployed faults"],
  [["OS CSPRNG + library [6, 7]", "none", "no", "no", "no"],
   ["Entropy authority [2]", "none", "at generation (protocol)", "certificate", "randomness at generation"],
   ["GAN-based PRNGs [13–16]", "learned generator", "no", "no", "no"],
   ["SP 800-90B health tests [9]", "none", "entropy source only", "no", "source-level"],
   ["**CryptoKMS (this work)**", "agentic validation", "yes", "verdict trail", "class-dependent (Table 5)"]],
  [2150, 1150, 1300, 1050, 1267]));

B.push(H1("3", "Methodology"));
B.push(H2("3.1", "System Architecture"));
B.push(P("CryptoKMS is a full-stack web service with a React front end, a FastAPI back end chosen for asynchronous handling of concurrent requests, and an API gateway that enforces validation before any key material reaches a client. Fig. 1 shows the issuance pipeline. Agents are stateless and independently replaceable; a failed validation returns an explicit error rather than degraded material, and every successful response embeds the per-agent verdict object so the client can log the evidence with the key."));
B.push(...figure("fig_pipeline.png", 372, 945, 1440, "Fig. 1.", "Validate-before-dispatch issuance pipeline. All checks operate on raw key material, and a key is dispatched only if every check passes."));
B.push(H2("3.2", "Agents"));
B.push(P("**KeyGeneratorAgent** draws symmetric keys from the operating-system CSPRNG (Python *secrets*) and constructs RSA (1024, 2048 or 4096 bits) and ECC (NIST P-256) keys with PyCryptodome. All checks run on raw material: AES key bytes, the ECC scalar *d* or the RSA modulus *n*. **MathModelAgent** computes the byte-level Shannon entropy *H* = −Σ *p*(*x*) log_{2} *p*(*x*) and the SP 800-22 Monobit test through the complementary error function [11]. **AIEntropyAgent** computes the bit-transition ratio *t*, the fraction of adjacent bit pairs that differ, which targets serial correlation that Monobit cannot observe because Monobit is invariant to bit order; despite its historical name it is a deterministic statistic, not a trained classifier. The **duplicate screen** keeps a SHA-256 index of issued raw material. **CryptoStrengthAgent** maps each key to its security strength under SP 800-57 (AES-256: 256 bits; ECC P-256: 128 bits; RSA-2048: 112 bits) [12], and **PerformanceAgent** records latency and retry count."));
B.push(H2("3.3", "Acceptance Rules"));
B.push(P("All thresholds are derived from the behaviour of a uniform source rather than tuned on evaluation data. The Monobit test accepts at significance α = 0.01. For *n* key bits from a uniform source, the *n* − 1 adjacent-pair indicators are independent Bernoulli(1/2) variables, so *t* has mean 0.5 and standard deviation σ_{t} = 0.5/√(*n* − 1); the acceptance band |*t* − 0.5| ≤ 2.576σ_{t} is the exact 99% two-sided normal interval (±0.081 at 256 bits)."));
B.push(P("The entropy rule needs more care. Byte entropy cannot exceed log_{2} min(256, *L*) for an *L*-byte sample, because *L* samples cannot populate more than *L* of the 256 symbols, so a fixed ceiling of 8.0 rejects every 32-byte key. However, log_{2} *L* is only an upper bound: the plug-in entropy estimator is biased downward for small samples [21], so 32 uniform bytes have expected entropy 4.882 rather than 5.0, and 256 uniform bytes have expected entropy 7.175 rather than 8.0. The original rule, here called *Rule A*, accepts *H* ≥ 0.9 · log_{2} min(256, *L*). Table 2 shows that Rule A happens to work for most key lengths but fails at exactly *L* = 256, the length of an RSA-2048 modulus, where 0.9 × 8.0 = 7.2 lies above the expected value and rejects 67.8% of uniform inputs. The corrected rule, *Rule B*, sets the threshold τ_{L} to the 0.1% quantile of *H_{L}* under a uniform source, estimated once per key length by Monte Carlo simulation with 200,000 samples that are independent of the evaluation keys. Rule B holds the entropy false-rejection rate near 0.1% for every key length by construction."));
B.push(caption("Table 2.", "Entropy reference for *L* uniform bytes. Thresholds in bits/byte; false-rejection rates measured on 20,000 independent uniform samples per length.", true));
B.push(table(
  ["*L*", "Key material", "log_{2} min(256, *L*)", "E[*H_{L}*] ± σ", "Rule A τ (false rej.)", "Rule B τ (false rej.)"],
  V.entropy_ref_rows.map((r, i) => i === 4 ? r.map((c, j) => j >= 4 ? `**${c}**` : c) : r),
  [430, 1700, 1050, 1180, 1270, 1287], { firstLeft: false }));
B.push(P("A key is accepted only if all three statistical checks pass and its raw material is absent from the duplicate index. Each statistical check costs *O*(*n*) in key bits and the duplicate screen *O*(1).", { first: true }));
B.push(H2("3.4", "Fail-Closed Issuance Loop"));
B.push(P("Algorithm 1 gives the issuance loop. Under a healthy generator each candidate is rejected with probability *p*_{0} ≈ 2% (Sect. 5.1), so the expected number of candidates per issued key is about 1.02, and ten consecutive rejections occur with probability of the order of 10^{−17}. Exhausting the loop is therefore treated not as bad luck but as an outage of the entropy source."));
B.push(...algorithm([
  "Input: algorithm A, key length L bytes, retry bound N = 10",
  "for attempt = 1 .. N do",
  "    k   <- Generate(A, L)        // OS CSPRNG / PyCryptodome",
  "    m   <- RawMaterial(k)        // AES bytes | ECC d | RSA n",
  "    okH <- H(m) >= tau_L         // Rule B (Table 2)",
  "    okM <- p_Monobit(m) >= 0.01  // SP 800-22 frequency test",
  "    okT <- |t(m) - 0.5| <= 2.576 * 0.5 / sqrt(8L - 1)",
  "    dup <- SHA256(m) in IssuedIndex",
  "    if okH and okM and okT and not dup then",
  "        register(m); attach verdicts; dispatch k; return",
  "raise EntropyFault               // fail closed: nothing dispatched",
]));
B.push(H2("3.5", "Scope of Rejection-Based Validation and Threat Model"));
B.push(P(`Rejection sampling cannot add entropy, and correct keys are rejected at the tests' false-positive rates by construction, so the pipeline is diagnostic rather than generative: a continuously running detector of faults and misconfiguration of the kind seen in [3, 4]. In scope are stuck-at faults, biased or under-seeded sources, substitution of a non-cryptographic generator, seed-space collapse and validation of encoded material, exactly the classes injected in Sect. 4. Out of scope are attacks that leave issued keys statistically clean: side-channel or memory disclosure [20], cryptanalytic breaks, and compromise of the validation service itself.`));
B.push(H2("3.6", "Key Lifecycle and Vault"));
B.push(P(`Accepted keys pass to a Firestore-backed vault that stores label, purpose, algorithm, timestamps and the verdict trail. Keys are masked by default, revocable instantly and rotated on schedules aligned with NIST and OWASP guidance [12, 17, 18], from 30 days for high-value credentials to 180 days for general encryption. Trust in the vault's root key is distributed by Shamir *M*-of-*N* secret sharing [22]. Keystroke dynamics serve only as an auxiliary access-risk signal, since deriving stable keys from noisy biometrics requires fuzzy extraction with attendant entropy loss [23].`));

B.push(H1("4", "Experimental Work"));
B.push(H2("4.1", "Environment and Reproducibility"));
B.push(new Paragraph({
  alignment: AlignmentType.JUSTIFIED, spacing: { before: 0, after: 0, line: 240 },
  children: [
    ...runs("All measurements were produced by a single self-contained evaluation script, released with the system implementation at "),
    new ExternalHyperlink({
      link: "https://github.com/khurramrashidd/Multi-Agent-Cryptographic-Key-Generator_v2",
      children: [new TextRun({ text: "github.com/khurramrashidd/Multi-Agent-Cryptographic-Key-Generator_v2", font: FONT, size: BODY })],
    }),
    ...runs(". The script implements every check from the specification above and writes all numbers and figures in Sect. 5. Environment: Linux on x86-64, Intel Xeon at 2.10 GHz, single thread, CPython 3.13, NumPy 2.5, SciPy 1.18 and PyCryptodome. All parameters (Sect. 3.3, Table 2, Algorithm 1) were fixed before measurement; seeded generators make the fault-injection and bias-sweep results exactly reproducible."),
  ],
}));
B.push(H2("4.2", "Datasets"));
B.push(P(`**Baseline.** 10,000 AES-256, 1,000 ECC P-256 and 200 RSA-2048 keys (11,200) from the production generation path. **Encodings.** The same ECC keys exported as PEM and DER, and the RSA keys as PEM. **Fault injection.** Five classes of 2,000 32-byte keys each (10,000 keys): a healthy CSPRNG control; a stuck-at fault emitting 0xAA\u2026AA; a biased source with P(1) = 0.55, modelling a degraded hardware generator; a fixed-seed Mersenne Twister, modelling substitution of a non-cryptographic generator; and a Debian-style pool of 2^{15} keys [3]. **Streams.** For the sequential alarm, 300 streams of 2,000 keys for the control and biased classes and 100 for the Mersenne Twister. **Bias sweep.** Nine levels from P(1) = 0.50 to 0.65, each with 5,000 keys and 200 streams.`));
B.push(H2("4.3", "Metrics"));
B.push(P(`*Per-key rejection* is the fraction of keys failing any check, broken down by check. *Duplicates* counts keys whose raw material repeats an earlier issuance. Because a healthy generator is also rejected about 2% of the time, a single rejection is not evidence of a fault, so detection is defined at the stream level. After *m* issuances with *r* rejections, the *sequential alarm* is raised when P(*X* ≥ *r*) < 10^{−3} for *X* ~ Binomial(*m*, *p*_{0}), where *p*_{0} = ${V.p0} is the healthy rejection rate measured on the 10,000-key AES baseline. *Keys-to-alarm* is the first *m* at which this occurs.`));

B.push(H1("5", "Result Analysis"));
B.push(H2("5.1", "Baseline Statistics"));
B.push(P(`Table 3 summarises the baseline. Monobit pass rates are indistinguishable from the nominal 99% level implied by \u03B1 = 0.01 (exact binomial *p* = 0.96, 0.52 and 0.14; every 95% Wilson interval contains 0.99), mean transition ratios lie within 0.001 of 0.5, and mean entropies match the uniform-source expectations of Table 2 within 0.002 bits/byte. Under Rule B, joint acceptance of healthy keys is 98.0% for AES-256 and ECC P-256 and 96.5% for RSA-2048, the false-positive cost of three checks near the 1% level.`));
B.push(caption("Table 3.", "Baseline pipeline statistics on raw key material.", true));
const BR = V.baseline_rows;
const brow = (label) => BR.find((r) => r[0] === label);
const mono = brow("Monobit pass"), mci = brow("95% Wilson CI");
const T4 = [brow("Samples"), brow("E[H_L], uniform source"), brow("Mean H ± sd (bits/byte)"),
  brow("Entropy pass, Rule A / Rule B"),
  ["Monobit pass [95% CI]", ...[1, 2, 3].map((i) => `${mono[i]} ${mci[i]}`)],
  brow("Binomial p vs. 0.99"), brow("Transition pass"), brow("Joint acceptance, Rule A / Rule B"),
  brow("Generation per key (ms)"), brow("Validation per key (ms)")];
B.push(table(["Metric", "AES-256 (*L* = 32)", "ECC P-256 (*L* = 32)", "RSA-2048 (*L* = 256)"],
  T4.map((r) => r.map(fixSub)), [2117, 1600, 1600, 1600]));
B.push(H2("5.2", "The Entropy Reference"));
B.push(P(`Fig. 2 makes the first correction visible. For 32-byte keys (panel a) the distribution sits well inside both thresholds, whereas a fixed 8.0 ceiling would reject all of them. For RSA-2048 moduli (panel b), the Rule A threshold of 7.2 lies above the expected value of 7.175, so only 31.0% of genuine moduli pass. Because the loop fails closed, this is not cosmetic: under Rule A each RSA-2048 key costs ${V.rsa_attempts_A} attempts on average, each a full prime search (288 ms here), and ${V.rsa_failclosed_A} of requests exhaust all ten attempts and return an error. Under Rule B entropy acceptance rises to 99.5%, joint acceptance to 96.5%, expected attempts fall to ${V.rsa_attempts_B} and the fail-closed probability becomes negligible (about 3 \u00D7 10^{\u221215}); for 32-byte keys the rules differ only in the far tail (99.97% versus 99.88%). Thresholds on plug-in entropy must therefore be referenced to the estimator's distribution at the actual sample length, not to its theoretical maximum.`));
B.push(...figure("fig_entropy.png", 412, 690, 1440, "Fig. 2.", "Measured byte entropy of raw key material. (a) AES-256, *L* = 32: both rules admit healthy keys. (b) RSA-2048 modulus, *L* = 256: the Rule A threshold lies above the expected entropy *E*[*H_{L}*] and rejects most genuine moduli; Rule B does not."));
B.push(H2("5.3", "The Encoding Artefact"));
B.push(P(`Testing exported encodings rather than raw material produces systematic false rejection (Table 4): the same ECC keys pass Monobit at 98.8% as raw scalars but at 0.0% as PEM and 1.5% as DER, and RSA-2048 falls from 98.0% to 0.0%. PEM is Base64 text, confining every byte to a 64-symbol printable alphabet with a persistent bit imbalance, and DER interleaves fixed ASN.1 headers with the secret. An earlier version of the system relaxed the rule for asymmetric keys to suppress these rejections, which, as the measurement shows, compensated for an encoding artefact and would have masked a defective generator. The corrected pipeline extracts the raw scalar or modulus first, so one strict policy serves all algorithms.`));
B.push(caption("Table 4.", "Effect of representation on identical keys.", true));
B.push(table(["Representation", "Monobit pass", "Mean *H* (bits/byte)"], V.enc_rows, [3317, 1800, 1800]));
B.push(H2("5.4", "Fault Injection"));
B.push(P(`Table 5 reports detection per generator class. The stuck-at generator is rejected on every key and raises the alarm after two; notably, the balanced 0xAA pattern passes Monobit and is caught only by the entropy and transition checks, so the checks are complementary rather than redundant. A bias of P(1) = 0.55 evades most single-key tests (17.8% per-key rejection, mostly Monobit), but because verdicts accumulate, the sequential alarm fires in all 300 streams after a median of 21 keys (95th percentile 66), while no healthy stream raised a false alarm within 2,000 issuances. Debian-style pool exhaustion is invisible to every per-key statistic, but the duplicate screen flagged 53 exact repeats among 2,000 issuances (59.8 expected).`));
B.push(P(`The Mersenne Twister is an explicit negative result: its rejection rate (1.80%) is indistinguishable from the control (1.95%) and it alarmed in 1 of 100 streams, yet its state can be reconstructed from 624 consecutive 32-bit outputs, that is, from 78 issued 256-bit keys. This is precisely the SP 800-22 caveat that statistical testing cannot substitute for cryptanalysis [11]. The pipeline therefore claims fault detection, never certification of unpredictability; deliberate generator substitution calls for provenance controls such as signed builds and attestation.`));
B.push(caption("Table 5.", "Detection by generator fault class (2,000 keys each). E / M / T: share of keys rejected by the entropy, Monobit and transition checks.", true));
B.push(table(["Generator class", "Per-key rejection", "Rejected by E / M / T (%)", "Duplicates", "Sequential alarm"],
  V.fault_rows.map((r) => r.map(fixSub)), [1700, 900, 1400, 1150, 1767]));
B.push(H2("5.5", "Detection Delay and Bias Sweep"));
const S = V.sweep;
B.push(P(`Fig. 3 extends the fault study across bias levels. Per-key rejection rises from the 2.0% baseline to ${S["0.52"].det} at P(1) = 0.52, ${S["0.55"].det} at 0.55 and ${S["0.60"].det} at 0.60. The sequential alarm converts these small per-key differences into reliable detection: at P(1) = 0.52 it fires in ${S["0.52"].rate} of streams within 2,000 keys (median ${S["0.52"].med} keys), at 0.53 in all streams (median ${S["0.53"].med}), at 0.55 after a median of ${S["0.55"].med} keys and at 0.60 after ${S["0.60"].med}. At P(1) = 0.51 it fires in only ${S["0.51"].rate} of streams. Continuous monitoring thus detects a bias of about two percentage points within a few hundred keys, which one-time certification cannot.`));
B.push(...figure("fig_bias_sweep.png", 372, 810, 1440, "Fig. 3.", "Bias sweep. Per-key rejection (left axis) and median keys to the sequential alarm (right axis, log scale), shown where at least 95% of 200 streams alarm within 2,000 keys."));
B.push(H2("5.6", "Overhead and Scalability"));
B.push(P(`Validation costs 0.031 ms per AES-256 or ECC key and 0.072 ms per RSA-2048 modulus, under 0.03% of RSA generation (288 ms of prime search). One thread sustains about ${V.thr_single} validated AES-256 keys per second on the per-key path and ${V.thr_batched} when batched, and since agents are stateless with cost linear in key bits, capacity scales with workers behind the asynchronous gateway.`));
B.push(H2("5.7", "Discussion and Limitations"));
B.push(P(`Three operational rules follow: alert on the aggregate acceptance rate, which a binomial alarm turns into detection of a two-point bias within hundreds of keys; treat any duplicate as an incident rather than a retry, since it was the only issuance-time signature of the Debian-class fault; and treat loop exhaustion as an outage of the entropy source. The evaluation is single-node, the per-key screen has limited power against mild bias, and no statistical screen certifies unpredictability.`));

B.push(H1("6", "Conclusion and Future Work"));
B.push(P(`CryptoKMS provides continuous, per-key, auditable evidence that a deployed key generator is still behaving correctly, as a validation layer complementary to learned generators. Three results transfer beyond this system: entropy thresholds must be referenced to the distribution of plug-in entropy at the actual sample length; validation must operate on raw key material rather than encodings; and issuance-time validation with a sequential alarm and duplicate screen detects stuck-at, biased and pool-collapse faults quickly, but cannot detect a statistically clean yet predictable generator. Future work will add the full SP 800-22 battery and SP 800-90B health tests [9, 11], the post-quantum standards ML-KEM (FIPS 203) [24] and ML-DSA (FIPS 204) [25], weak-key corpus checks [4], and hardware security module integration so that private keys never reside in plaintext memory [20].`));

// Springer requires a disclosure statement
B.push(new Paragraph({
  spacing: { before: 240, after: 0, line: 220 }, alignment: AlignmentType.JUSTIFIED,
  children: [new TextRun({ text: "Disclosure of Interests. ", font: FONT, size: SMALL, bold: true }),
    new TextRun({ text: "The authors have no competing interests to declare that are relevant to the content of this article.", font: FONT, size: SMALL })],
}));

// ---------- references (Springer LNCS/LNNS style, order of first citation) ----------
const REFS = [
  "Stallings, W.: Cryptography and Network Security: Principles and Practice, 7th edn. Pearson, Boston (2017)",
  "Corrigan-Gibbs, H., Mu, W., Boneh, D., Ford, B.: Ensuring high-quality randomness in cryptographic key generation. In: Proceedings of the 2013 ACM SIGSAC Conference on Computer and Communications Security (CCS), pp. 685–696. ACM, New York (2013)",
  "Debian Security Advisory DSA-1571-1: OpenSSL – predictable random number generator (CVE-2008-0166) (2008), https://www.debian.org/security/2008/dsa-1571",
  "Heninger, N., Durumeric, Z., Wustrow, E., Halderman, J.A.: Mining your Ps and Qs: detection of widespread weak keys in network devices. In: Proceedings of the 21st USENIX Security Symposium, pp. 205–220. USENIX Association (2012)",
  "Shumow, D., Ferguson, N.: On the possibility of a back door in the NIST SP800-90 Dual Ec Prng. CRYPTO 2007 Rump Session, Santa Barbara (2007)",
  "Schneier, B.: Applied Cryptography: Protocols, Algorithms, and Source Code in C, 2nd edn. Wiley, New York (1996)",
  "OpenSSL Project: OpenSSL cryptography and SSL/TLS toolkit documentation, https://www.openssl.org/docs/",
  "Barker, E., Kelsey, J.: Recommendation for random number generation using deterministic random bit generators. NIST Special Publication 800-90A Rev. 1, NIST, Gaithersburg (2015)",
  "Sönmez Turan, M., Barker, E., Kelsey, J., McKay, K.A., Baish, M.L., Boyle, M.: Recommendation for the entropy sources used for random bit generation. NIST Special Publication 800-90B, NIST, Gaithersburg (2018)",
  "Barker, E., Kelsey, J., McKay, K., Roginsky, A., Sönmez Turan, M.: Recommendation for random bit generator (RBG) constructions. NIST Special Publication 800-90C, NIST, Gaithersburg (2025). https://doi.org/10.6028/NIST.SP.800-90C",
  "Rukhin, A., et al.: A statistical test suite for random and pseudorandom number generators for cryptographic applications. NIST Special Publication 800-22 Rev. 1a, NIST, Gaithersburg (2010)",
  "Barker, E.: Recommendation for key management: Part 1 – General. NIST Special Publication 800-57 Part 1 Rev. 5, NIST, Gaithersburg (2020)",
  "De Bernardi, M., Khouzani, M.H.R., Malacaria, P.: Pseudo-random number generation using generative adversarial networks. In: ECML PKDD 2018 Workshops. LNCS, vol. 11329, pp. 191–200. Springer, Cham (2019)",
  "Kim, H., Kwon, Y., Sim, M., Lim, S., Seo, H.: Generative adversarial networks-based pseudo-random number generator for embedded processors. In: Information Security and Cryptology – ICISC 2020. LNCS, vol. 12593, pp. 215–234. Springer, Cham (2021)",
  "Oak, R., Rahalkar, C., Gujar, D.: Poster: using generative adversarial networks for secure pseudorandom number generation. In: Proceedings of the 2019 ACM SIGSAC Conference on Computer and Communications Security (CCS), pp. 2597–2599. ACM, New York (2019)",
  "Fei, C., Zhang, X., Wang, D., Hu, H., Huang, R., Wang, Z.: EPRNG: effective pseudo-random number generator on the Internet of Vehicles using deep convolution generative adversarial network. Information 16(1), 21 (2025). https://doi.org/10.3390/info16010021",
  "OWASP Foundation: OWASP Top 10 web application security risks (2021), https://owasp.org/www-project-top-ten/",
  "Amazon Web Services: Best practices for managing AWS access keys, https://docs.aws.amazon.com/general/latest/gr/aws-access-keys-best-practices.html",
  "Capital One Financial Corporation: Capital One announces data security incident. Press release, 29 July 2019",
  "Synopsys: The Heartbleed bug (CVE-2014-0160) (2014), https://heartbleed.com/",
  "Paninski, L.: Estimation of entropy and mutual information. Neural Computation 15(6), 1191–1253 (2003)",
  "Shamir, A.: How to share a secret. Communications of the ACM 22(11), 612–613 (1979)",
  "Dodis, Y., Ostrovsky, R., Reyzin, L., Smith, A.: Fuzzy extractors: how to generate strong keys from biometrics and other noisy data. SIAM Journal on Computing 38(1), 97–139 (2008)",
  "National Institute of Standards and Technology: Module-lattice-based key-encapsulation mechanism standard. FIPS 203, NIST, Gaithersburg (2024)",
  "National Institute of Standards and Technology: Module-lattice-based digital signature standard. FIPS 204, NIST, Gaithersburg (2024)",
];
const refHead = new Paragraph({
  keepNext: true, spacing: { before: 360, after: 180 },
  children: [new TextRun({ text: "References", font: FONT, size: 24, bold: true })],
});
const refs = REFS.map((r) => new Paragraph({
  numbering: { reference: "refs", level: 0 },
  alignment: AlignmentType.LEFT, spacing: { before: 0, after: 0, line: 216 },
  children: [new TextRun({ text: r, font: FONT, size: SMALL })],
}));

const doc = new Document({
  creator: "Khurram Rashid",
  title: "CryptoKMS: A Multi-Agent Validate-Before-Dispatch Framework for Fault-Aware Cryptographic Key Issuance in Secure Communication Systems",
  styles: { default: { document: { run: { font: FONT, size: BODY } } } },
  numbering: {
    config: [{
      reference: "refs",
      levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.RIGHT,
        style: { paragraph: { indent: { left: 397, hanging: 397 } }, run: { font: FONT, size: SMALL } } }],
    }],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 2948, bottom: 2948, left: 2495, right: 2494, header: 1418, footer: 1418 },
      },
    },
    children: [...front, ...B, refHead, ...refs],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("written", OUT);
});
