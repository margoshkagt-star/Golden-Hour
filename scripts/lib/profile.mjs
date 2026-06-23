// Parse users/<user_key>/profile.md (semi-structured markdown).

function parseScalar(raw) {
  const s = raw.trim();
  if (s === "" || s === "null") return null;
  if (s === "true") return true;
  if (s === "false") return false;
  if (/^\d+(\.\d+)?$/.test(s)) return Number(s);
  if (s.startsWith("[") && s.endsWith("]")) {
    try {
      return JSON.parse(s.replace(/'/g, '"'));
    } catch {
      return s;
    }
  }
  if (
    (s.startsWith('"') && s.endsWith('"')) ||
    (s.startsWith("'") && s.endsWith("'"))
  ) {
    return s.slice(1, -1);
  }
  return s;
}

function isSubLine(line) {
  return /^\s{2,}/.test(line) && line.trim() !== "";
}

function parseSubBlock(lines, start) {
  const map = {};
  const list = [];
  let i = start;
  let mode = null;

  while (i < lines.length) {
    const line = lines[i];
    if (!isSubLine(line) && line.trim() !== "" && !line.startsWith("<!--")) {
      break;
    }
    if (line.trim() === "" || line.startsWith("<!--")) {
      i++;
      continue;
    }

    const trimmed = line.trim();
    const listMap = trimmed.match(/^-\s+"([^"]+)":\s*(.+)$/);
    if (listMap) {
      mode = "map";
      map[listMap[1]] = parseScalar(listMap[2]);
      i++;
      continue;
    }

    const bareMap = trimmed.match(/^"([^"]+)":\s*(.+)$/);
    if (bareMap) {
      mode = "map";
      map[bareMap[1]] = parseScalar(bareMap[2]);
      i++;
      continue;
    }

    const listItem = trimmed.match(/^-\s+(.+)$/);
    if (listItem) {
      mode = mode || "list";
      list.push(parseScalar(listItem[1]));
      i++;
      continue;
    }

    i++;
  }

  if (mode === "map" || Object.keys(map).length) return { value: map, end: i };
  if (list.length) return { value: list, end: i };
  return { value: null, end: start };
}

export function parseProfile(text) {
  const profile = {};
  const lines = text.replace(/\r\n/g, "\n").split("\n");

  for (let i = 0; i < lines.length; i++) {
    const m = lines[i].match(/^-\s+\*\*([^*]+):\*\*\s*(.*)$/);
    if (!m) continue;

    const key = m[1].trim();
    const rest = m[2].trim();

    if (rest === "" || rest === "null") {
      const sub = parseSubBlock(lines, i + 1);
      if (sub.value != null) {
        profile[key] = sub.value;
        i = sub.end - 1;
        continue;
      }
      profile[key] = null;
      continue;
    }

    profile[key] = parseScalar(rest);
  }

  return profile;
}

export function loadProfile(userDir, readText) {
  const p = `${userDir}/profile.md`;
  const text = readText(p);
  if (!text) return { exists: false, path: p, profile: null };
  return { exists: true, path: p, profile: parseProfile(text) };
}

export function getSetupStatus(profile) {
  return profile?.setup_status || profile?.["setup_status"] || "new";
}

/** PNG theme for study-plan-cards / table-cards: light | dark */
/** @deprecated Use CARD_THEME from card-render.mjs — single built-in dark style. */
export function getCardTheme(_profile) {
  return "dark";
}

export function getTopicsFromProfile(profile) {
  const purpose = profile.purpose;
  if (purpose === "exam") {
    let topics = profile.exam_topics;
    if (typeof topics === "string") {
      try {
        topics = JSON.parse(topics.replace(/'/g, '"'));
      } catch {
        topics = [topics];
      }
    }
    if (!Array.isArray(topics)) topics = [];
    const levels = profile.exam_topic_levels || {};
    return topics.map((title) => ({
      title,
      level: levels[title] ?? levels[String(title)] ?? "medium",
    }));
  }

  if (purpose === "olympiad") {
    const levels = profile.olympiad_levels || profile.olympiad_topic_levels;
    if (levels && typeof levels === "object" && !Array.isArray(levels)) {
      return Object.entries(levels).map(([title, level]) => ({ title, level }));
    }
    const subject = profile.olympiad_subject || "предмет";
    const level = profile.olympiad_level || "medium";
    return defaultOlympiadTopics(subject, level);
  }

  if (purpose === "topic") {
    const sub = profile.topic_sublevels;
    if (sub && typeof sub === "object" && !Array.isArray(sub)) {
      return Object.entries(sub).map(([title, level]) => ({ title, level }));
    }
    const main = profile.study_topic || profile.study_subject || "тема";
    return [
      {
        title: main,
        level: profile.topic_level || "medium",
      },
    ];
  }

  return [];
}

function defaultOlympiadTopics(subject, defaultLevel) {
  const blocks = {
    math: ["Алгебра", "Геометрия", "Комбинаторика", "Теория чисел"],
    physics: ["Механика", "Термодинамика", "Электродинамика", "Оптика"],
    informatics: ["Структуры данных", "Динамическое программирование", "Графы"],
    chemistry: ["Неорганическая химия", "Органическая химия", "Расчётные задачи"],
    biology: ["Ботаника", "Зоология", "Анатомия", "Генетика"],
    russian: ["Орфография", "Пунктуация", "Стилистика"],
  };
  const key = String(subject || "").toLowerCase();
  const titles = blocks[key] || [`Подготовка: ${subject}`];
  return titles.map((title) => ({ title, level: defaultLevel }));
}

export function matchTopicKey(title, map) {
  if (!map || typeof map !== "object") return null;
  if (map[title] != null) return title;

  const t = String(title).toLowerCase();
  let best = null;
  let bestScore = 0;

  for (const key of Object.keys(map)) {
    const k = key.toLowerCase();
    if (k === t) return key;
    if (k.includes(t) || t.includes(k)) {
      const score = Math.min(k.length, t.length);
      if (score > bestScore) {
        bestScore = score;
        best = key;
      }
      continue;
    }
    const words = t.split(/[^a-zа-яё0-9]+/i).filter((w) => w.length > 3);
    const hits = words.filter((w) => k.includes(w)).length;
    if (hits > bestScore) {
      bestScore = hits;
      best = key;
    }
  }
  return best;
}

export function topicField(profile, title, field) {
  const map = profile[field];
  if (!map || typeof map !== "object") return undefined;
  const key = matchTopicKey(title, map);
  return key ? map[key] : undefined;
}

export function getLevelMap(profile) {
  const purpose = profile.purpose;
  if (purpose === "exam") return profile.exam_topic_levels || {};
  if (purpose === "olympiad") {
    return profile.olympiad_levels || profile.olympiad_topic_levels || {};
  }
  if (purpose === "topic") {
    const sub = profile.topic_sublevels;
    if (sub && typeof sub === "object") return sub;
    const main = profile.study_topic || "тема";
    return { [main]: profile.topic_level || "medium" };
  }
  return {};
}
