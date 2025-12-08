// routes/dashboard.js
import express from "express";

export default function dashboardRoute(collection) {
  const router = express.Router();

  // ---------- Category keywords (multi-language, expand as needed) ----------
  const categories = {
    Scholarship: [
      "scholarship","stipend","financial aid","grant","fee waiver",
      "உதவித்தொகை","छात्रवृत्ति","స్కాలర్‌షిప్","ವಿದ್ಯಾರ್ಥಿ ವೇತನ","સ્કોલરશિપ","বৃত্তি"
    ],
    Exams: [
      "exam","test","result","marks","hall ticket","timetable",
      "தேர்வு","परीक्षा","పరీక్ష","ಪರೀಕ್ಷೆ","પरीક્ષા","পরীক্ষা"
    ],
    Hostel: [
      "hostel","room","mess","warden","accommodation",
      "விடுதி","हॉस्टल","హాస్టల్","ವಸತಿ","હોસ્ટેલ","হোস্টেল"
    ],
    Library: [
      "library","book","borrow","return","fine",
      "நூலகம்","पुस्तकालय","లైబ్రరీ","ಗ್ರಂಥಾಲಯ","લાઇબ્રેરી","গ্রন্থাগার"
    ],
    Fees: [
      "fee","fees","payment","due","receipt",
      "கட்டணம்","फ़ीस","ఫీజు","ಶುಲ್ಕ","ફી","ফি"
    ],
    Admission: [
      "admission","apply","application","register","enroll",
      "சேர்க்கை","प्रवेश","ప్రవేశం","ಪ್ರವೇಶ","એડમિશન","ভর্তি"
    ],
    Courses: [
      "course","subject","syllabus","semester","credits",
      "பாடம்","पाठ्यक्रम","కోర్సు","ಪಠ್ಯಕ್ರಮ","કોર્સ","কোর্স"
    ],
    Management: [
      "management","principal","hod","office","administration",
      "நிர்வாகம்","प्रबंधन","నిర్వహణ","ನಿರ್ವಹಣೆ","વ્યવસ્થાપન","প্রশাসন"
    ],
    Counselling: [
      "counsel","counselling","guidance","mentor","career help",
      "ஆலோசனை","परामर्श","సలహా","ಮಾರ್ಗದರ್ಶನ","કાઉન્સેલિંગ","পরামর্শ"
    ],
    Food: [
      "food","mess food","canteen","breakfast","lunch","dinner",
      "உணவு","खाना","ఆహారం","ಆಹಾರ","ભોજન","খাবার"
    ],
    Teaching: [
      "teaching","faculty","teacher","professor","lecture",
      "கற்பித்தல்","शिक्षण","బోధన","ಬೋಧನೆ","શિક્ષણ","পাঠদান"
    ]
  };

  // ---------- Greetings to ignore when counting total queries ----------
  const greetingWords = [
    "hi","hello","hey","good morning","good evening",
    "vanakkam","namaste","hai","hola","bonjour"
  ].map(w => w.toLowerCase());

  // ---------- Phrases that indicate escalation in AI reply ----------
  // extend this list if your AI uses other phrases for escalation
  const escalationPhrases = [
    "i apologize, the information is not available",
    "i'm sorry, the information is not available",
    "the information is not available in the college",
    "i will forward to admin",
    "forwarding to admin",
    "i will escalate",
    "please contact admin",
    "i cannot find",
    "unable to find",
    "not available in the college database",
    "i'll pass this to admin",
  ].map(s => s.toLowerCase());

  // ---------- Simple language detection by Unicode script ranges ----------
  // returns language key used in frontend (English, Hindi, Tamil, Telugu, Kannada, Gujarati, Bengali, Malayalam, Others)
  function detectLanguageFromText(text) {
    if (!text || typeof text !== "string") return "Others";

    // check scripts
    if (/\p{Script=Devanagari}/u.test(text)) return "Hindi";
    if (/\p{Script=Tamil}/u.test(text)) return "Tamil";
    if (/\p{Script=Telugu}/u.test(text)) return "Telugu";
    if (/\p{Script=Kannada}/u.test(text)) return "Kannada";
    if (/\p{Script=Gujarati}/u.test(text)) return "Gujarati";
    if (/\p{Script=Bengali}/u.test(text)) return "Bengali";
    if (/\p{Script=Malayalam}/u.test(text)) return "Malayalam";
    // fallback: if contains ASCII letters it's likely English
    if (/[A-Za-z]/.test(text)) return "English";
    return "Others";
  }

  // ---------- Helper: safely extract text from message data ----------
  function extractTextFromMsgData(msgData) {
    // Common shapes we've seen in your DB:
    // msg.data === "some string"
    // msg.data === { content: "text", ... }
    // msg.data === { content: "...", response_metadata: {...} }
    // msg.data may have nested objects from tool outputs; prefer .content if present
    if (!msgData) return "";

    if (typeof msgData === "string") return msgData;
    if (typeof msgData === "object") {
      // common key names to try
      const keys = ["content", "text", "message", "reply", "answer", "data"];
      for (const k of keys) {
        if (typeof msgData[k] === "string" && msgData[k].trim().length > 0) {
          return msgData[k];
        }
      }
      // sometimes content sits deeper inside e.g. msg.data.response.content
      // try to find the first string leaf
      const queue = [msgData];
      while (queue.length) {
        const node = queue.shift();
        for (const v of Object.values(node)) {
          if (typeof v === "string" && v.trim().length > 0) return v;
          if (v && typeof v === "object") queue.push(v);
        }
      }
    }
    return "";
  }

  // ---------- Colors for categories (frontend consumes these) ----------
  const categoryColors = {
    Scholarship: "#8b5cf6",
    Exams: "#3b82f6",
    Hostel: "#10b981",
    Library: "#f59e0b",
    Fees: "#ef4444",
    Admission: "#6366f1",
    Courses: "#14b8a6",
    Management: "#9333ea",
    Counselling: "#0ea5e9",
    Food: "#22c55e",
    Teaching: "#f97316",
    Others: "#6b7280",
  };

  // ---------- API: /stats ----------
  router.get("/stats", async (req, res) => {
    try {
      // total unique users
      const totalUsers = await collection.distinct("sessionId").then(arr => arr.length);

      // fetch docs
      const docs = await collection.find({}).toArray();

      // initial counters
      let totalQueries = 0; // human messages excluding greetings
      const categoryCounts = {};
      Object.keys(categories).forEach(k => (categoryCounts[k] = 0));
      let othersCount = 0;

      // language counts (based on human messages)
      const langCounts = {
        English: 0,
        Hindi: 0,
        Tamil: 0,
        Telugu: 0,
        Kannada: 0,
        Gujarati: 0,
        Bengali: 0,
        Malayalam: 0,
        Others: 0
      };

      // AI accuracy / escalation counters
      let aiResponses = 0;
      let escalations = 0;

      // loop messages
      for (const doc of docs) {
        if (!Array.isArray(doc.messages)) continue;

        for (const msg of doc.messages) {
          if (!msg || !msg.type) continue;

          // HUMAN messages -> count queries & classify
          if (msg.type === "human") {
            const raw = extractTextFromMsgData(msg.data);
            const text = (raw || "").toString().trim();
            if (!text) continue;

            const lower = text.toLowerCase();

            // skip pure greetings (exact match or very short greetings)
            const isGreeting =
              greetingWords.includes(lower) ||
              // also skip if contains only greeting + punctuation
              (lower.split(/\s+/).every(w => greetingWords.includes(w)) && lower.length < 30);

            if (isGreeting) continue;

            // count it
            totalQueries++;

            // language detection (for human message)
            const lang = detectLanguageFromText(text);
            if (langCounts[lang] !== undefined) langCounts[lang] += 1;
            else langCounts.Others += 1;

            // category matching
            let matched = false;
            for (const [cat, keywords] of Object.entries(categories)) {
              for (const kw of keywords) {
                if (!kw) continue;
                // match simple substring (keywords are already multilingual)
                if (lower.includes(kw.toLowerCase())) {
                  categoryCounts[cat] += 1;
                  matched = true;
                  break;
                }
              }
              if (matched) break;
            }
            if (!matched) othersCount++;
          }

          // AI messages -> used for accuracy / human escalation detection
          if (msg.type === "ai") {
            const rawAI = extractTextFromMsgData(msg.data);
            const textAI = (rawAI || "").toString().trim();
            if (!textAI) continue;

            aiResponses++;

            const lowAI = textAI.toLowerCase();
            // if it matches any escalation phrase, count as escalation
            if (escalationPhrases.some(p => lowAI.includes(p))) {
              escalations++;
            }
          }
        }
      } // end docs loop

      // compute accuracy
      let accuracy = 0;
      if (aiResponses > 0) {
        accuracy = ((aiResponses - escalations) / aiResponses) * 100;
        // fix weird >100 cases and NaN
        if (!isFinite(accuracy) || Number.isNaN(accuracy)) accuracy = 0;
        if (accuracy < 0) accuracy = 0;
        if (accuracy > 100) accuracy = 100;
      }
      // format to 2 decimals (number)
      const accuracyFormatted = Number(accuracy.toFixed(2));

      // prepare language distribution: percentages based on totalQueries
      const totalLangCount = Object.values(langCounts).reduce((a, b) => a + b, 0);
      const languages = Object.entries(langCounts).map(([lang, count]) => ({
        language: lang,
        count,
        percentage: totalLangCount > 0 ? Number(((count / totalLangCount) * 100).toFixed(1)) : 0
      }));

      // prepare categories array for frontend
      const finalCategories = [
        ...Object.entries(categoryCounts).map(([key, count]) => ({
          category: key,
          count,
          color: categoryColors[key] || "#999999"
        })),
        {
          category: "Others",
          count: othersCount,
          color: categoryColors.Others
        }
      ];

      // final JSON
      return res.json({
        totalUsers,
        totalQueries,
        categories: finalCategories,
        languages,
        accuracy: accuracyFormatted,
        human_escalations: escalations,
        ai_responses: aiResponses
      });
    } catch (err) {
      console.error("Dashboard Error:", err);
      return res.status(500).json({ error: "Dashboard calculation failed" });
    }
  });

  return router;
}