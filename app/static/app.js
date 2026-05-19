// --- API helpers ---
const API = {
  get: url => fetch(url).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e))),
  post: (url, data) => fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  }).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e))),
  delete: url => fetch(url, { method: "DELETE" }).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e)))
  ,put: (url, data) => fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  }).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e)))
};



// --- Tab switching (two-level: top tabs + sub-tabs) ---
const subTabState = { learn: 'lookup', manage: 'input' };

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const topTab = btn.dataset.tab;

    document.querySelectorAll('.tab-content').forEach(s => s.classList.remove('active'));
    document.getElementById('tab-' + topTab).classList.add('active');

    document.querySelectorAll('.sub-tabs').forEach(st => st.classList.remove('visible'));
    const subNav = document.getElementById('sub-tabs-' + topTab);
    if (subNav) subNav.classList.add('visible');

    if (subNav) {
      const remembered = subTabState[topTab];
      const targetBtn = subNav.querySelector('[data-subtab="' + remembered + '"]') || subNav.querySelector('.sub-tab');
      if (targetBtn) targetBtn.click();
    }

    if (topTab === 'browse') loadBrowseTree();
  });
});

// --- Sub-tab switching ---
document.querySelectorAll('.sub-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    const parentNav = btn.closest('.sub-tabs');
    const topTab = parentNav.id.replace('sub-tabs-', '');
    subTabState[topTab] = btn.dataset.subtab;

    parentNav.querySelectorAll('.sub-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const topContent = document.getElementById('tab-' + topTab);
    topContent.querySelectorAll('.subtab-content').forEach(s => s.classList.remove('active'));
    const subContent = document.getElementById('subtab-' + btn.dataset.subtab);
    if (subContent) subContent.classList.add('active');

    const sub = btn.dataset.subtab;
    if (sub === 'vocab') loadVocab();
    if (sub === 'settings') loadMgmtTree();
    if (sub === 'excluded') loadExcludedWords();
    if (sub === 'migrate') loadExportBooks();
  });
});

// --- Input tab ---
let currentBooks = [];

async function loadBooks() {
  currentBooks = await API.get("/api/books");
  const sel = document.getElementById("sel-book");
  sel.innerHTML = "<option value=\"\">-- 请选择或新建 --</option>";
  currentBooks.forEach(b => {
    sel.innerHTML += "<option value=\"" + escAttr(b.id) + "\">" + esc(b.name) + "</option>";
  });
}

document.getElementById("sel-book").addEventListener("change", async function() {
  const bookId = parseInt(this.value);
  if (!bookId) { clearUnits(); clearLessons(); return; }
  const units = await API.get("/api/books/" + bookId + "/units");
  const sel = document.getElementById("sel-unit");
  sel.innerHTML = "<option value=\"\">-- 请选择或新建 --</option>";
  units.forEach(u => {
    var label = u.title ? ("单元 " + u.unit_no + " " + esc(u.title)) : ("单元 " + u.unit_no);
    sel.innerHTML += "<option value=\"" + escAttr(u.id) + "\">" + label + "</option>";
  });
  clearLessons();
});

document.getElementById("sel-unit").addEventListener("change", async function() {
  const unitId = parseInt(this.value);
  if (!unitId) { clearLessons(); return; }
  const lessons = await API.get("/api/units/" + unitId + "/lessons");
  const sel = document.getElementById("sel-lesson");
  sel.innerHTML = "<option value=\"\">-- 请选择或新建 --</option>";
  lessons.forEach(l => {
    var label = l.title ? ("课" + l.lesson_no + " " + esc(l.title)) : ("课" + l.lesson_no);
    sel.innerHTML += "<option value=\"" + escAttr(l.id) + "\">" + label + "</option>";
  });
});

function clearUnits() {
  document.getElementById("sel-unit").innerHTML = "<option value=\"\">-- 请选择或新建 --</option>";
  clearLessons();
}
function clearLessons() {
  document.getElementById("sel-lesson").innerHTML = "<option value=\"\">-- 请选择或新建 --</option>";
}

// Save & Analyze
document.getElementById("btn-save-text").addEventListener("click", async () => {
  var bookId = parseInt(document.getElementById("sel-book").value);
  var unitId = parseInt(document.getElementById("sel-unit").value);
  var lessonId = parseInt(document.getElementById("sel-lesson").value);
  const content = document.getElementById("inp-content").value.trim();
  const textType = document.getElementById("sel-text-type").value;

  if (!content) { alert("请输入课文内容。"); return; }

  try {
    if (!bookId) {
      const name = document.getElementById("inp-book-name").value.trim();
      if (!name) { alert("请选择或创建教材。"); return; }
      const res = await API.post("/api/books", {
        name: name,
        publisher: document.getElementById("inp-publisher").value.trim() || null,
        grade: document.getElementById("inp-grade").value.trim() || null,
        semester: document.getElementById("inp-semester").value.trim() || null,
      });
      bookId = res.id;
      await loadBooks();
    }
    if (!unitId) {
      const unitNo = parseInt(document.getElementById("inp-unit-no").value);
      if (!unitNo) { alert("请输入单元号。"); return; }
      const res = await API.post("/api/units", {
        book_id: bookId, unit_no: unitNo,
        title: document.getElementById("inp-unit-title").value.trim() || null,
      });
      unitId = res.id;
    }
    if (!lessonId) {
      const lessonNo = parseInt(document.getElementById("inp-lesson-no").value);
      if (!lessonNo) { alert("请输入课次号。"); return; }
      const res = await API.post("/api/lessons", {
        unit_id: unitId, lesson_no: lessonNo,
        title: document.getElementById("inp-lesson-title").value.trim() || null,
      });
      lessonId = res.id;
    }

    const result = await API.post("/api/lessons/" + lessonId + "/text", { content: content, text_type: textType });
    const div = document.getElementById("input-result");
    div.style.display = "block";
    var html = "<p><strong>已保存到:</strong> " + esc(result.path) + "</p>";
    if (result.new_words.length > 0) {
      html += "<p><strong>新单词 (" + result.new_words.length + "):</strong> ";
      result.new_words.forEach(w => {
       const forms = result.word_forms[w] || [w];
        var extraForms = forms.filter(function(f) { return f.toLowerCase() !== w.toLowerCase(); });
        html += "<span class=\"new-word-tag\">" + esc(w) + (extraForms.length > 0 ? ": " + esc(extraForms.join(", ")) : "") + "</span> ";
     });
      html += "</p>";
    } else {
      html += "<p style=\"color:var(--text-light)\">本课无新单词（全部为复习词或停用词）。</p>";
    }
    div.innerHTML = html;
  } catch (e) {
    alert("错误: " + (e.detail || JSON.stringify(e)));
  }
});

// --- Lookup tab ---
let lookupTimer = null;
document.getElementById("inp-word").addEventListener("input", () => {
  clearTimeout(lookupTimer);
  lookupTimer = setTimeout(lookupWord, 300);
});

async function lookupWord() {
  const word = document.getElementById("inp-word").value.trim().toLowerCase();
  const div = document.getElementById("lookup-result");
  if (!word) { div.style.display = "none"; return; }
  try {
    const result = await API.get("/api/words/" + encodeURIComponent(word));
    div.style.display = "block";
    var html = "<div class=\"word-header\">" + esc(result.word) + "</div>";
    if (result.first_lesson_path) {
      html += "<div class=\"word-path\">📖 首次出现: " + esc(result.first_lesson_path) + "</div>";
    }
    html += "<div class=\"word-stat\">出现 " + result.total_count + " 次</div>";
    if (result.forms && result.forms.length > 0) {
      html += "<div class=\"word-forms\">词形变化: ";
      result.forms.forEach(f => {
        html += "<span class=\"form-tag\">" + esc(f.form) + " <small>(" + f.count + ")</small></span> ";
      });
      html += "</div>";
    }
    if (result.lessons && result.lessons.length > 0) {
      html += "<ul class=\"lesson-list\">";
      result.lessons.forEach(l => {
        html += "<li>";
        html += "<div class=\"lesson-item-header\">" + esc(l.path) + " <span class=\"badge\">" + l.count + "次</span></div>";
        if (l.contexts && l.contexts.length > 0) {
          html += "<div class=\"context-group\">";
          l.contexts.forEach(ctx => {
            var highlighted = highlightWord(ctx, result.word, result.forms);
            html += "<div class=\"context-line\">" + highlighted + "</div>";
          });
          html += "</div>";
        }
        html += "</li>";
      });
      html += "</ul>";
    }
    div.innerHTML = html;
  } catch (e) {
    div.style.display = "block";
    div.innerHTML = "<p style=\"color:var(--text-light)\">未找到单词 \"" + esc(word) + "\"</p>";
  }
}

// --- Browse tab ---
async function loadBrowseTree() {
  const container = document.getElementById("browse-tree");
  const books = await API.get("/api/books");
  if (books.length === 0) {
    container.innerHTML = "<p style=\"color:var(--text-light)\">还没有教材，请先录入课文。</p>";
    return;
  }
  var html = "";
  for (var bi = 0; bi < books.length; bi++) {
    const book = books[bi];
    html += "<div class=\"tree-book\">";
    html += "<div class=\"tree-book-header\" onclick=\"toggleNext(this)\">";
    html += "<span class=\"tree-book-title\">📚 " + esc(book.name) + "</span>";
    html += "<span class=\"browse-summary\">";
    html += "<span class=\"stat-badge stat-unit\">" + book.total_units + " 单元</span>";
    html += "<span class=\"stat-badge stat-lesson\">" + book.total_lessons + " 课</span>";
    html += "<span class=\"stat-badge stat-new\">" + book.new_count + " 新词</span>";
    html += "</span>";
    html += "</div>";
    const units = await API.get("/api/books/" + book.id + "/units");
    for (var ui = 0; ui < units.length; ui++) {
      const unit = units[ui];
      var uLabel = unit.title ? ("单元 " + unit.unit_no + " " + unit.title) : ("单元 " + unit.unit_no);
      html += "<div class=\"tree-unit\" style=\"display:none\">";
      html += "<div class=\"tree-unit-header\" onclick=\"toggleNext(this)\">";
      html += "<span class=\"tree-unit-title\">📖 " + esc(uLabel) + "</span>";
      html += "<span class=\"browse-summary\">";
      html += "<span class=\"stat-badge stat-lesson\">" + unit.lesson_count + " 课</span>";
      html += "<span class=\"stat-badge stat-new\">" + unit.new_count + " 新词</span>";
      html += "<span class=\"stat-badge stat-review\">" + unit.review_count + " 复习</span>";
      html += "</span>";
      html += "</div>";
      html += "<div class=\"unit-detail-btn\"><button class=\"btn-sm\" onclick=\"toggleUnitWordDetail(" + unit.id + ", this)\">📋 单词详情</button></div>";
      html += "<div class=\"unit-word-detail\" id=\"unit-detail-" + unit.id + "\" style=\"display:none\"></div>";
      const lessons = await API.get("/api/units/" + unit.id + "/lessons");
      html += "<div style=\"display:none\">";
      for (var li = 0; li < lessons.length; li++) {
        const lesson = lessons[li];
        var lLabel = lesson.title ? ('课' + lesson.lesson_no + ' ' + lesson.title) : ('课' + lesson.lesson_no);
        html += '<div class="tree-lesson">';
        html += '<div class="tree-lesson-info" onclick="toggleLessonDetail(' + lesson.id + ')">' + esc(lLabel) + ' <span class="id-badge">[ID:' + lesson.id + ']</span></div>';
        html += '<div class="tree-lesson-detail" id="lesson-detail-' + lesson.id + '">加载中...</div>';
        html += '</div>';
      }
      html += '</div></div>';
    }
    html += '</div>';
  }
  container.innerHTML = html;
}

function toggleNext(el) {
  var siblings = el.parentElement.children;
  for (var i = 0; i < siblings.length; i++) {
    if (siblings[i] !== el) {
      siblings[i].style.display = siblings[i].style.display === 'none' ? 'block' : 'none';
    }
  }
}

﻿
async function toggleUnitWordDetail(unitId, btn) {
  var panel = document.getElementById('unit-detail-' + unitId);
  if (panel.style.display !== 'none' && panel.innerHTML !== '') {
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    btn.textContent = panel.style.display === 'none' ? '﻿⬇ 单词详情' : '⬆ 收起详情';
    return;
  }
  btn.textContent = '加载中...';
  try {
    var data = await API.get('/api/units/' + unitId + '/word-detail');
    var html = '<div class="unit-detail-content">';
    html += '<div class="unit-detail-stats">';
    html += '<span class="stat-badge stat-new">新单词 ' + data.new_count + '</span>';
    html += '<span class="stat-badge stat-review">复习单词 ' + data.review_count + '</span>';
    html += '</div>';
    if (data.new_words.length > 0) {
      html += '<div class="unit-detail-section"><strong>新单词列表：</strong></div>';
      html += '<div class="unit-word-list">';
      data.new_words.forEach(function(w) {
       html += '<span class="new-word-tag">' + esc(w.word);
        var extraForms = (w.forms || []).filter(function(f) { return f.toLowerCase() !== w.word.toLowerCase(); });
        if (extraForms.length > 0) {
          html += ' <span class="word-forms-sub">(' + esc(extraForms.join(', ')) + ')</span>';
        }
        html += '</span> ';
      });
      html += '</div>';
    }
    if (data.review_words.length > 0) {
      html += '<div class="unit-detail-section"><strong>复习单词：</strong></div>';
      html += '<div class="unit-word-list">';
      data.review_words.forEach(function(w) {
        html += '<span class="review-word-tag">' + esc(w) + '</span> ';
      });
      html += '</div>';
    }
    if (data.lessons && data.lessons.length > 0) {
      html += '<div class="unit-detail-section" style="margin-top:12px"><strong>各课明细：</strong></div>';
      data.lessons.forEach(function(l) {
        var lLabel = l.title ? ('课' + l.lesson_no + ' ' + l.title) : ('课' + l.lesson_no);
        html += '<div class="unit-lesson-breakdown">';
        html += '<div class="unit-lesson-title">' + esc(lLabel) + '</div>';
        if (l.new_words.length > 0) {
          html += '<div><span class="stat-badge stat-new" style="font-size:0.8em">新 ' + l.new_words.length + '</span> ';
          html += l.new_words.map(function(w){ return esc(w); }).join(', ');
          html += '</div>';
        }
        if (l.review_words.length > 0) {
          html += '<div><span class="stat-badge stat-review" style="font-size:0.8em">复习 ' + l.review_words.length + '</span> ';
          html += l.review_words.map(function(w){ return esc(w); }).join(', ');
          html += '</div>';
        }
        if (l.new_words.length === 0 && l.review_words.length === 0) {
          html += '<div style="color:var(--text-light);font-size:0.85em">暂无单词数据</div>';
        }
        html += '</div>';
      });
    }
    html += '</div>';
    panel.innerHTML = html;
    panel.style.display = 'block';
    btn.textContent = '⬆ 收起详情';
  } catch (e) {
    panel.innerHTML = '<span style="color:var(--danger)">加载失败</span>';
    panel.style.display = 'block';
    btn.textContent = '⬇ 单词详情';
  }
}

async function toggleLessonDetail(lessonId) {
  var detail = document.getElementById('lesson-detail-' + lessonId);
  if (detail.classList.contains('open')) { detail.classList.remove('open'); return; }
  try {
    const results = await Promise.all([
      API.get('/api/lessons/' + lessonId + '/text').catch(function() { return null; }),
      API.get('/api/lessons/' + lessonId + '/words')
    ]);
    var textData = results[0];
    var wordData = results[1];
    var html = '';
    if (textData) {
      html += '<strong>课文:</strong>\n' + esc(textData.content) + '\n\n';
    }
    if (wordData.new_words.length > 0) {
      html += '<strong>新单词 (' + wordData.new_words.length + '):</strong> ';
      wordData.new_words.forEach(w => {
       const forms = wordData.word_forms[w] || [w];
        var extraForms = forms.filter(function(f) { return f.toLowerCase() !== w.toLowerCase(); });
        html += '<span class="new-word-tag">' + esc(w) + (extraForms.length > 0 ? ': ' + esc(extraForms.join(', ')) : '') + '</span> ';
     });
    }
    if (wordData.review_words && wordData.review_words.length > 0) {
      html += '<strong>复习单词 (' + wordData.review_words.length + '):</strong> ' + esc(wordData.review_words.join(', '));
    }
    detail.innerHTML = html;
  } catch (e) {
    detail.innerHTML = '<span style="color:var(--danger)">加载失败</span>';
  }
  detail.classList.add('open');
}

document.getElementById('btn-import').addEventListener('click', async () => {
  const text = document.getElementById('inp-batch').value.trim();
  if (!text) { alert('请粘贴导入文本。'); return; }
  try {
    const result = await API.post('/api/import/batch', { text: text });
    const div = document.getElementById('import-result');
    div.style.display = 'block';
    var html = '<p><strong>导入成功！共 ' + result.imported + ' 节课!</strong></p>';
    result.entries.forEach(e => {
      html += '<div class="import-entry">' + esc(e.book_name) + ' U' + e.unit_no + ' L' + e.lesson_no + ' - ' + e.new_word_count + ' 个新词</div>';
    });
    div.innerHTML = html;
    document.getElementById('inp-batch').value = '';
  } catch (e) { alert('导入错误: ' + (e.detail || JSON.stringify(e))); }
});

document.getElementById('btn-rebuild').addEventListener('click', async () => {
  if (!confirm('确认重建单词索引？')) return;
  try {
    const result = await API.post('/api/rebuild', {});
    const div = document.getElementById('rebuild-result');
    div.style.display = 'block';
    div.innerHTML = '<p style="color:var(--primary)">重建完成！共处理 ' + result.total_words + ' 个词元。</p>';
  } catch (e) { alert('错误: ' + (e.detail || JSON.stringify(e))); }
});

function highlightWord(sentence, word, forms) {
  if (!sentence) return "";
  var words = [word];
  if (forms && forms.length) {
    forms.forEach(function(f) {
      if (f.form) words.push(f.form);
    });
  }
  var escaped = words.map(function(w) { return w.replace(/[.*+?^${}()|[\]\\]/g, "\$&"); });
   var pattern = new RegExp("\\b(" + escaped.join("|") + ")\\b", "gi");
  return sentence.replace(pattern, '<span class="highlight">$1</span>');
}

function esc(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

// --- Vocab Tab ---
async function loadVocab() {
  var q = document.getElementById('inp-vocab-search').value.trim();
  var sort = document.getElementById('sel-vocab-sort').value;
  var params = new URLSearchParams();
  if (q) params.set('q', q);
  params.set('sort', sort);
  try {
    var data = await API.get('/api/vocab?' + params.toString());
    renderVocabTable(data);
  } catch (e) {
    document.getElementById('vocab-result').innerHTML = '<p style="color:var(--danger)">加载失败</p>';
  }
}

function renderVocabTable(words) {
  if (words.length === 0) {
    document.getElementById('vocab-result').innerHTML = '<p style="color:var(--text-light)">还没有学过的单词</p>';
    return;
  }
  var html = '<p class="vocab-summary">共 ' + words.length + ' 个单词</p>';
  html += '<table class="vocab-table"><thead><tr>';
  html += '<th>单词</th><th>词形变化</th><th>上下文</th><th>首次出现</th><th>次数</th>';
  html += '</tr></thead><tbody>';
  for (var i = 0; i < words.length; i++) {
    var w = words[i];
    html += '<tr>';
    html += '<td class="word-cell">' + esc(w.word) + '</td>';
    var formsHtml = '';
    if (w.forms && w.forms.length > 0) {
      formsHtml = w.forms.map(function(f) { return '<span class="form-tag">' + esc(f.form) + '</span>'; }).join(' ');
    }
    html += '<td>' + formsHtml + '</td>';
    // Context column with highlighted word
    var ctxHtml = '-';
    if (w.context) {
      var ctxWords = [w.word];
      if (w.forms && w.forms.length) w.forms.forEach(function(f) { if (f.form) ctxWords.push(f.form); });
      ctxHtml = highlightWord(w.context, w.word, w.forms);
    }
    html += '<td class="vocab-context">' + ctxHtml + '</td>';
    html += '<td>' + esc(w.first_lesson_path || '-') + '</td>';
    html += '<td><span class="vocab-count">' + w.total_count + '</span></td>';
    html += '<td><button class="btn-sm btn-exclude" onclick="excludeVocabWord(' + w.id + ',\x27' + escAttr(w.word).replace(/'/g, String.fromCharCode(39)) + '\x27, this)">🚫 排除</button></td>';
    html += '</tr>';
  }
  html += '</tbody></table>';
  document.getElementById('vocab-result').innerHTML = html;
}

document.getElementById('inp-vocab-search').addEventListener('input', function() {
  clearTimeout(window._vocabTimer);
  window._vocabTimer = setTimeout(loadVocab, 300);
});
document.getElementById('sel-vocab-sort').addEventListener('change', loadVocab);

// --- Quiz Tab ---
var quizState = {
  mode: null,
  words: [],
  current: 0,
  results: [],
  knownCount: 0,
  unknownCount: 0
};

function resetQuizUI() {
  document.getElementById('quiz-mode-area').style.display = 'block';
  document.getElementById('quiz-play-area').style.display = 'none';
  document.getElementById('quiz-result-area').style.display = 'none';
  document.getElementById('mistakes-list-area').style.display = 'none';
  document.getElementById('lesson-picker').style.display = 'none';
  document.getElementById('quiz-count-picker').style.display = 'none';
}

async function startQuiz(mode) {
  if (mode === 'random') {
    // Show count picker
    document.getElementById('quiz-count-picker').style.display = 'block';
    document.getElementById('lesson-picker').style.display = 'none';
    window._pendingQuizMode = 'random';
    return;
  }
  _doStartQuiz(mode);
}

async function confirmRandomQuiz() {
  await _doStartQuiz('random');
}

async function _doStartQuiz(mode) {
  resetQuizUI();
  document.getElementById('quiz-mode-area').style.display = 'none';
  document.getElementById('quiz-play-area').style.display = 'block';

  var data;
  if (mode === 'random') {
    var countEl = document.getElementById('sel-quiz-count');
    var count = countEl ? parseInt(countEl.value) : 10;
    data = await API.get('/api/quiz/random?count=' + count);
  } else if (mode === 'mistakes') {
    data = await API.get('/api/quiz/mistakes');
    if (data.words.length === 0) {
      resetQuizUI();
      alert('错题本为空，快去测验吧！');
      return;
    }
  } else {
    return;
  }

  quizState = {
    mode: mode,
    words: data.words,
    current: 0,
    results: [],
    knownCount: 0,
    unknownCount: 0
  };
  showQuizWord(0);
}

function showLessonPicker() {
  var picker = document.getElementById('lesson-picker');
  var countPicker = document.getElementById('quiz-count-picker');
  countPicker.style.display = 'none';
  picker.style.display = picker.style.display === 'none' ? 'block' : 'none';
  if (picker.style.display === 'block') loadQuizBooks();
}

async function loadQuizBooks() {
  var books = await API.get('/api/books');
  var sel = document.getElementById('sel-quiz-book');
  sel.innerHTML = '<option value="">-- 选教材 --</option>';
  books.forEach(function(b) {
    sel.innerHTML += '<option value="' + escAttr(b.id) + '">' + esc(b.name) + '</option>';
  });
}

document.getElementById('sel-quiz-book').addEventListener('change', async function() {
  var bookId = parseInt(this.value);
  if (!bookId) return;
  var units = await API.get('/api/books/' + bookId + '/units');
  window._quizUnits = units;
  var sel = document.getElementById('sel-quiz-unit');
  sel.innerHTML = '<option value="">-- 选单元 --</option>';
  sel.innerHTML += '<option value="all">全部单元</option>';
  units.forEach(function(u) {
    sel.innerHTML += '<option value="' + escAttr(u.id) + '">' + esc(u.title ? ('单元 ' + u.unit_no + ' ' + u.title) : ('单元 ' + u.unit_no)) + '</option>';
  });
  var lessonSel = document.getElementById('sel-quiz-lesson');
  lessonSel.innerHTML = '<option value="">-- 选课 --</option>';
});

document.getElementById('sel-quiz-unit').addEventListener('change', async function() {
  var unitVal = this.value;
  if (!unitVal) return;
  var sel = document.getElementById('sel-quiz-lesson');
  sel.innerHTML = '<option value="">-- 选课 --</option>';
  sel.innerHTML += '<option value="all">全部课节</option>';
  if (unitVal === 'all') {
    if (!window._quizUnits) return;
    window._quizUnits.forEach(function(u) {
      if (u.lessons) {
        u.lessons.forEach(function(l) {
          var prefix = u.title ? ('单元' + u.unit_no + ' ' + u.title + ' ') : ('单元' + u.unit_no + ' ');
          sel.innerHTML += '<option value="' + escAttr(l.id) + '">' + esc(prefix + (l.title ? ('课' + l.lesson_no + ' ' + l.title) : ('课' + l.lesson_no))) + '</option>';
        });
      }
    });
  } else {
    var unitId = parseInt(unitVal);
    var lessons = await API.get('/api/units/' + unitId + '/lessons');
    lessons.forEach(function(l) {
      sel.innerHTML += '<option value="' + escAttr(l.id) + '">' + esc(l.title ? ('课' + l.lesson_no + ' ' + l.title) : ('课' + l.lesson_no)) + '</option>';
    });
  }
});

async function startLessonQuiz() {
  var bookId = parseInt(document.getElementById('sel-quiz-book').value);
  if (!bookId) { alert('请选择教材'); return; }
  var unitVal = document.getElementById('sel-quiz-unit').value;
  var lessonVal = document.getElementById('sel-quiz-lesson').value;
  var lessonIds = [];
  if (lessonVal === 'all' && unitVal === 'all') {
    if (window._quizUnits) {
      window._quizUnits.forEach(function(u) {
        if (u.lessons) u.lessons.forEach(function(l) { lessonIds.push(l.id); });
      });
    }
  } else if (lessonVal === 'all' && unitVal !== 'all') {
    var unitId = parseInt(unitVal);
    var unit = window._quizUnits ? window._quizUnits.find(function(u) { return u.id === unitId; }) : null;
    if (unit && unit.lessons) {
      unit.lessons.forEach(function(l) { lessonIds.push(l.id); });
    }
  } else if (lessonVal && lessonVal !== 'all') {
    lessonIds.push(parseInt(lessonVal));
  } else {
    if (unitVal === 'all') {
      if (window._quizUnits) {
        window._quizUnits.forEach(function(u) {
          if (u.lessons) u.lessons.forEach(function(l) { lessonIds.push(l.id); });
        });
      }
    } else if (unitVal) {
      var unitId2 = parseInt(unitVal);
      var unit2 = window._quizUnits ? window._quizUnits.find(function(u) { return u.id === unitId2; }) : null;
      if (unit2 && unit2.lessons) {
        unit2.lessons.forEach(function(l) { lessonIds.push(l.id); });
      }
    }
  }
  if (lessonIds.length === 0) { alert('没有找到课节'); return; }
  resetQuizUI();
  document.getElementById('quiz-mode-area').style.display = 'none';
  document.getElementById('quiz-play-area').style.display = 'block';
  var data;
  if (lessonIds.length === 1) {
    data = await API.get('/api/quiz/lesson/' + lessonIds[0]);
  } else {
    data = await API.get('/api/quiz/lessons?lesson_ids=' + lessonIds.join(','));
  }
  if (data.words.length === 0) {
    resetQuizUI();
    alert('没有单词'); return;
  }
  var shuffle = document.getElementById('chk-quiz-shuffle');
  if (shuffle && shuffle.checked) {
    for (var i = data.words.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = data.words[i]; data.words[i] = data.words[j]; data.words[j] = tmp;
    }
  }
  quizState = {
    mode: 'lesson',
    words: data.words,
    current: 0,
    results: [],
    lessonId: lessonIds.length === 1 ? lessonIds[0] : null,
    knownCount: 0,
    unknownCount: 0
  };
  showQuizWord(0);
}

function showQuizWord(index) {
  var word = quizState.words[index];
  document.getElementById('quiz-word').textContent = word.word;
  var formsHtml = '';
  if (word.forms && word.forms.length > 0) {
    formsHtml = word.forms.map(function(f) { return '<span class="form-tag">' + esc(f) + '</span>'; }).join(' ');
  }
  document.getElementById('quiz-forms').innerHTML = formsHtml;
  document.getElementById('quiz-hint').style.display = 'none';
  document.getElementById('quiz-hint-btn').style.display = 'inline-block';

  var total = quizState.words.length;
  var pct = Math.round((index / total) * 100);
  document.getElementById('quiz-progress-bar').style.width = pct + '%';
  document.getElementById('quiz-progress-text').textContent = (index + 1) + '/' + total;
}

function showQuizHint() {
  var word = quizState.words[quizState.current];
  var hint = '';
  if (word.first_lesson_path) {
    hint += '首次出现: ' + word.first_lesson_path;
  }
  hint += ' | 出现次数: ' + (word.total_count || 0);
  document.getElementById('quiz-hint').textContent = hint;
  document.getElementById('quiz-hint').style.display = 'block';
  document.getElementById('quiz-hint-btn').style.display = 'none';
}

async function submitAnswer(result) {
  var word = quizState.words[quizState.current];
  var quizType = quizState.mode;
  var lessonId = quizState.mode === 'lesson' ? quizState.lessonId : null;

  await API.post('/api/quiz/result', {
    word_id: word.id,
    result: result,
    quiz_type: quizType,
    lesson_id: lessonId
  });

  if (result === 'known') {
    quizState.knownCount++;
  } else {
    quizState.unknownCount++;
  }
  quizState.results.push({ word: word, result: result });

  quizState.current++;
  if (quizState.current >= quizState.words.length) {
    showQuizResult();
  } else {
    showQuizWord(quizState.current);
  }
}

function showQuizResult() {
  document.getElementById('quiz-play-area').style.display = 'none';
  document.getElementById('quiz-result-area').style.display = 'block';

  var total = quizState.words.length;
  var pct = Math.round((quizState.knownCount / total) * 100);
  var html = '<div class="quiz-result-summary">';
  html += '<p class="big-num green">' + quizState.knownCount + '</p><p>认识</p>';
  html += '<p class="big-num red">' + quizState.unknownCount + '</p><p>不认识</p>';
  html += '<p style="font-size:1.2em;margin-top:8px">正确率: <strong>' + pct + '%</strong></p>';
  html += '</div>';

  if (quizState.unknownCount > 0) {
    html += '<div class="quiz-wrong-list"><p style="font-weight:600;margin-bottom:8px">答错的单词:</p>';
    for (var i = 0; i < quizState.results.length; i++) {
      if (quizState.results[i].result === 'unknown') {
        html += '<span class="quiz-wrong-item">' + esc(quizState.results[i].word.word) + '</span> ';
      }
    }
    html += '</div>';
    html += '<button class="btn-warning" style="margin-top:12px" onclick="startQuiz(\'mistakes\')">错题重测</button> ';
  }
  html += '<button class="btn-primary" style="margin-top:12px" onclick="resetQuizUI()">返回</button>';

  document.getElementById('quiz-result-area').innerHTML = html;
}

// --- Mistakes List ---
async function loadMistakes() {
  resetQuizUI();
  document.getElementById('mistakes-list-area').style.display = 'block';
  try {
    var words = await API.get('/api/mistakes');
    renderMistakesList(words);
  } catch (e) {
    document.getElementById('mistakes-list').innerHTML = '<p style="color:var(--danger)">加载失败</p>';
  }
}

function renderMistakesList(words) {
  if (words.length === 0) {
    document.getElementById('mistakes-list').innerHTML = '<p class="mistake-empty">🎉 错题本为空，全部掌握！</p>';
    return;
  }
  var html = '';
  for (var i = 0; i < words.length; i++) {
    var w = words[i];
    var formsStr = w.forms ? w.forms.join(', ') : '';
    html += '<div class="mistake-item">';
    html += '<span class="mistake-word">' + esc(w.word) + '</span>';
    html += '<span class="mistake-forms">' + esc(formsStr) + '</span>';
    if (w.latest_time) {
      html += '<span class="mistake-time">' + esc(w.latest_time) + '</span>';
    }
    html += '<button class="mistake-remove-btn" onclick="clearMistake(' + w.id + ')">移除</button>';
    html += '</div>';
  }
  document.getElementById('mistakes-list').innerHTML = html;
}

async function clearMistake(wordId) {
  try {
    await API.delete('/api/mistakes/' + wordId);
    loadMistakes();
  } catch (e) {
    alert('操作失败');
  }
}


// --- Management tab ---
let mgmtData = { books: [], units: {}, lessons: {} };

async function loadMgmtTree() {
  var container = document.getElementById('mgmt-tree');
  container.innerHTML = '<p style="color:var(--text-light)">加载中...</p>';
  try {
    var books = await API.get('/api/books');
    mgmtData.books = books;
    mgmtData.units = {};
    mgmtData.lessons = {};
    if (books.length === 0) {
      container.innerHTML = '<p style="color:var(--text-light)">还没有教材，请先录入课文。</p>';
      return;
    }
    var html = '';
    for (var bi = 0; bi < books.length; bi++) {
      var book = books[bi];
      html += '<div class="mgmt-book">';
      html += '<div class="mgmt-item">';
      html += '<span class="mgmt-toggle" onclick="mgmtToggle(this)">▶</span>';
      html += '<span class="mgmt-item-label">📚 ' + esc(book.name) + '</span>';
      html += '<div class="mgmt-actions">';
      html += '<button class="btn-sm btn-edit" onclick="editBook(' + book.id + ')">✏️ 编辑</button>';
      html += '<button class="btn-sm btn-danger" onclick="delBook(' + book.id + ')">🗑️ 删除</button>';
      html += '</div></div>';
      html += '<div class="mgmt-children" style="display:none" id="mgmt-book-' + book.id + '">';
      html += '<p style="color:var(--text-light);font-size:0.85em">加载中...</p>';
      html += '</div></div>';
    }
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<p style="color:var(--danger)">加载失败: ' + esc(e.detail || String(e)) + '</p>';
  }
}

async function mgmtToggle(el) {
  var childrenDiv = el.parentElement.nextElementSibling;
  if (!childrenDiv) return;
  var isHidden = childrenDiv.style.display === 'none';
  childrenDiv.style.display = isHidden ? 'block' : 'none';
  el.textContent = isHidden ? '▼' : '▶';
  if (isHidden && childrenDiv.querySelector('p')) {
    var bookId = parseInt(childrenDiv.id.replace('mgmt-book-', ''));
    await loadMgmtUnits(bookId);
  }
}

async function loadMgmtUnits(bookId) {
  var container = document.getElementById('mgmt-book-' + bookId);
  if (!container) return;
  try {
    var units = await API.get('/api/books/' + bookId + '/units');
    mgmtData.units[bookId] = units;
    var html = '';
    for (var ui = 0; ui < units.length; ui++) {
      var unit = units[ui];
      var uLabel = unit.title ? ('单元 ' + unit.unit_no + ' ' + unit.title) : ('单元 ' + unit.unit_no);
      html += '<div class="mgmt-unit">';
      html += '<div class="mgmt-item">';
      html += '<span class="mgmt-toggle" onclick="mgmtToggleUnit(this, ' + unit.id + ')">▶</span>';
      html += '<span class="mgmt-item-label">📖 ' + esc(uLabel) + '</span>';
      html += '<div class="mgmt-actions">';
      if (ui > 0) html += '<button class="btn-sm btn-up" onclick="moveUnit(' + bookId + ',' + unit.id + ',-1)">⬆</button>';
      if (ui < units.length - 1) html += '<button class="btn-sm btn-down" onclick="moveUnit(' + bookId + ',' + unit.id + ',1)">⬇</button>';
      html += '<button class="btn-sm btn-edit" onclick="editUnit(' + unit.id + ')">✏️</button>';
      html += '<button class="btn-sm btn-danger" onclick="delUnit(' + unit.id + ')">🗑️</button>';
      html += '</div></div>';
      html += '<div class="mgmt-children" style="display:none" id="mgmt-unit-' + unit.id + '">';
      html += '<p style="color:var(--text-light);font-size:0.85em">加载中...</p>';
      html += '</div></div>';
    }
    if (units.length === 0) {
      html = '<p style="color:var(--text-light);font-size:0.85em;margin-left:20px">暂无单元</p>';
    }
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<p style="color:var(--danger)">加载失败</p>';
  }
}

async function mgmtToggleUnit(el, unitId) {
  var childrenDiv = el.parentElement.nextElementSibling;
  if (!childrenDiv) return;
  var isHidden = childrenDiv.style.display === 'none';
  childrenDiv.style.display = isHidden ? 'block' : 'none';
  el.textContent = isHidden ? '▼' : '▶';
  if (isHidden && childrenDiv.querySelector('p')) {
    await loadMgmtLessons(unitId);
  }
}

async function loadMgmtLessons(unitId) {
  var container = document.getElementById('mgmt-unit-' + unitId);
  if (!container) return;
  try {
    var lessons = await API.get('/api/units/' + unitId + '/lessons');
    mgmtData.lessons[unitId] = lessons;
    var html = '';
    for (var li = 0; li < lessons.length; li++) {
      var lesson = lessons[li];
      var lLabel = lesson.title ? ('课' + lesson.lesson_no + ' ' + lesson.title) : ('课' + lesson.lesson_no);
      html += '<div class="mgmt-item">';
      html += '<span class="mgmt-item-label">📄 ' + esc(lLabel) + '</span>';
      html += '<div class="mgmt-actions">';
      if (li > 0) html += '<button class="btn-sm btn-up" onclick="moveLesson(' + unitId + ',' + lesson.id + ',-1)">⬆</button>';
      if (li < lessons.length - 1) html += '<button class="btn-sm btn-down" onclick="moveLesson(' + unitId + ',' + lesson.id + ',1)">⬇</button>';
      html += '<button class="btn-sm btn-text" onclick="viewLessonText(' + lesson.id + ')">📝 正文</button>';
      html += '<button class="btn-sm btn-edit" onclick="editLesson(' + lesson.id + ')">✏️</button>';
      html += '<button class="btn-sm btn-danger" onclick="delLesson(' + lesson.id + ')">🗑️</button>';
      html += '</div></div>';
    }
    if (lessons.length === 0) {
      html = '<p style="color:var(--text-light);font-size:0.85em;margin-left:20px">暂无课次</p>';
    }
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<p style="color:var(--danger)">加载失败</p>';
  }
}

// --- Inline editing ---
function editBook(bookId) {
  var book = mgmtData.books.find(function(b) { return b.id === bookId; });
  if (!book) return;
  var item = event.target.closest('.mgmt-item');
  var label = item.querySelector('.mgmt-item-label');
  var actions = item.querySelector('.mgmt-actions');
  label.innerHTML = '<div class="inline-edit">' +
    '<input id="edit-book-name" value="' + escAttr(book.name || '') + '" placeholder="教材名称">' +
    '<input id="edit-book-pub" value="' + escAttr(book.publisher || '') + '" placeholder="出版社">' +
    '<input id="edit-book-grade" value="' + escAttr(book.grade || '') + '" placeholder="年级">' +
    '<input id="edit-book-sem" value="' + escAttr(book.semester || '') + '" placeholder="学期">' +
    '<button class="btn-sm btn-edit" onclick="saveBook(' + bookId + ')">💾 保存</button>' +
    '<button class="btn-sm" onclick="loadMgmtTree()" style="background:#eee">取消</button>' +
    '</div>';
  actions.style.display = 'none';
}

async function saveBook(bookId) {
  try {
    var data = {};
    var name = document.getElementById('edit-book-name').value.trim();
    var pub = document.getElementById('edit-book-pub').value.trim();
    var grade = document.getElementById('edit-book-grade').value.trim();
    var sem = document.getElementById('edit-book-sem').value.trim();
    if (name) data.name = name;
    data.publisher = pub || null;
    data.grade = grade || null;
    data.semester = sem || null;
    await API.put('/api/books/' + bookId, data);
    loadMgmtTree();
  } catch (e) {
    alert('保存失败: ' + (e.detail || String(e)));
  }
}

function editUnit(unitId) {
  var unit = null;
  for (var bk in mgmtData.units) {
    var found = mgmtData.units[bk].find(function(u) { return u.id === unitId; });
    if (found) { unit = found; break; }
  }
  if (!unit) return;
  var item = event.target.closest('.mgmt-item');
  var label = item.querySelector('.mgmt-item-label');
  var actions = item.querySelector('.mgmt-actions');
  label.innerHTML = '<div class="inline-edit">' +
    '<input id="edit-unit-no" type="number" value="' + escAttr(unit.unit_no) + '" placeholder="单元号" style="width:70px">' +
    '<input id="edit-unit-title" value="' + escAttr(unit.title || '') + '" placeholder="单元标题">' +
    '<button class="btn-sm btn-edit" onclick="saveUnit(' + unitId + ')">💾 保存</button>' +
    '<button class="btn-sm" onclick="loadMgmtTree()" style="background:#eee">取消</button>' +
    '</div>';
  actions.style.display = 'none';
}

async function saveUnit(unitId) {
  try {
    var data = {};
    var no = parseInt(document.getElementById('edit-unit-no').value);
    var title = document.getElementById('edit-unit-title').value.trim();
    if (no) data.unit_no = no;
    data.title = title || null;
    await API.put('/api/units/' + unitId, data);
    loadMgmtTree();
  } catch (e) {
    alert('保存失败: ' + (e.detail || String(e)));
  }
}

function editLesson(lessonId) {
  var lesson = null;
  for (var uk in mgmtData.lessons) {
    var found = mgmtData.lessons[uk].find(function(l) { return l.id === lessonId; });
    if (found) { lesson = found; break; }
  }
  if (!lesson) return;
  var item = event.target.closest('.mgmt-item');
  var label = item.querySelector('.mgmt-item-label');
  var actions = item.querySelector('.mgmt-actions');
  label.innerHTML = '<div class="inline-edit">' +
    '<input id="edit-lesson-no" type="number" value="' + escAttr(lesson.lesson_no) + '" placeholder="课次号" style="width:70px">' +
    '<input id="edit-lesson-title" value="' + escAttr(lesson.title || '') + '" placeholder="课次标题">' +
    '<button class="btn-sm btn-edit" onclick="saveLesson(' + lessonId + ')">💾 保存</button>' +
    '<button class="btn-sm" onclick="loadMgmtTree()" style="background:#eee">取消</button>' +
    '</div>';
  actions.style.display = 'none';
}

async function saveLesson(lessonId) {
  try {
    var data = {};
    var no = parseInt(document.getElementById('edit-lesson-no').value);
    var title = document.getElementById('edit-lesson-title').value.trim();
    if (no) data.lesson_no = no;
    data.title = title || null;
    await API.put('/api/lessons/' + lessonId, data);
    loadMgmtTree();
  } catch (e) {
    alert('保存失败: ' + (e.detail || String(e)));
  }
}

// --- Delete ---
async function delBook(bookId) {
  var book = mgmtData.books.find(function(b) { return b.id === bookId; });
  if (!book) return;
  if (!confirm('确定删除教材《' + book.name + '》及其所有单元、课次和课文？此操作不可撤销。')) return;
  try {
    var result = await API.delete('/api/books/' + bookId);
    alert('已删除《' + result.name + '》（含 ' + result.units + ' 个单元、' + result.lessons + ' 个课次）');
    loadMgmtTree();
  } catch (e) {
    alert('删除失败: ' + (e.detail || String(e)));
  }
}

async function delUnit(unitId) {
  if (!confirm('确定删除该单元及其所有课次和课文？此操作不可撤销。')) return;
  try {
    var result = await API.delete('/api/units/' + unitId);
    alert('已删除单元 ' + result.unit_no + '（含 ' + result.lessons + ' 个课次）');
    loadMgmtTree();
  } catch (e) {
    alert('删除失败: ' + (e.detail || String(e)));
  }
}

async function delLesson(lessonId) {
  if (!confirm('确定删除该课次及其课文内容？此操作不可撤销。')) return;
  try {
    var result = await API.delete('/api/lessons/' + lessonId);
    alert('已删除课' + result.lesson_no);
    loadMgmtTree();
  } catch (e) {
    alert('删除失败: ' + (e.detail || String(e)));
  }
}

// --- Lesson Text View/Edit ---
var textEditState = { lessonId: null, texts: [] };

async function viewLessonText(lessonId) {
  var panel = document.getElementById('text-edit-panel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'text-edit-panel';
    panel.className = 'text-edit-panel';
    var mgmtTree = document.getElementById('mgmt-tree');
    mgmtTree.parentNode.insertBefore(panel, mgmtTree.nextSibling);
  }
  textEditState.lessonId = lessonId;
  try {
    var result = await API.get('/api/lessons/' + lessonId + '/texts');
    textEditState.texts = result.texts || [];
    var path = result.path || '';
    var html = '<div class="text-edit-header">';
    html += '<span class="text-edit-path">📂 ' + esc(path) + '</span>';
    html += '<button class="btn-sm" onclick="closeTextPanel()" style="background:#eee">✕ 关闭</button>';
    html += '</div>';
    if (textEditState.texts.length === 0) {
      html += '<div class="text-edit-empty">暂无正文内容</div>';
      html += '<button class="btn-primary" onclick="addTextType(&apos;main&apos;)">+ 正文</button>';
    } else {
      for (var i = 0; i < textEditState.texts.length; i++) {
        var t = textEditState.texts[i];
        var typeLabel = t.text_type === 'main' ? '正文' : t.text_type === 'dialogue' ? '对话' : '单词表';
        html += '<div class="text-edit-type-block">';
        html += '<div class="text-edit-type-header">';
        html += '<span class="text-edit-type-label">📝 ' + typeLabel + '</span>';
        html += '<button class="btn-sm btn-text-save" onclick="saveText(&apos;' + t.text_type + '&apos;)">💾 保存</button>';
        html += '</div>';
        html += '<textarea id="text-area-' + t.text_type + '" class="text-edit-area" rows="8">' + esc(t.content) + '</textarea>';
        html += '</div>';
      }
      html += '<div class="text-edit-add-row">';
      if (!textEditState.texts.find(function(x) { return x.text_type === 'main'; })) {
        html += '<button class="btn-sm" onclick="addTextType(&apos;main&apos;)">+ 正文</button>';
      }
      if (!textEditState.texts.find(function(x) { return x.text_type === 'dialogue'; })) {
        html += '<button class="btn-sm" onclick="addTextType(&apos;dialogue&apos;)">+ 对话</button>';
      }
      if (!textEditState.texts.find(function(x) { return x.text_type === 'words'; })) {
        html += '<button class="btn-sm" onclick="addTextType(&apos;words&apos;)">+ 单词表</button>';
      }
      html += '</div>';
    }
    panel.innerHTML = html;
    panel.style.display = 'block';
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    alert('加载失败: ' + (e.detail || String(e)));
  }
}

function closeTextPanel() {
  var panel = document.getElementById('text-edit-panel');
  if (panel) panel.style.display = 'none';
}

function addTextType(type) {
  textEditState.texts.push({ text_type: type, content: '' });
  viewLessonText(textEditState.lessonId);
}

async function saveText(textType) {
  var textarea = document.getElementById('text-area-' + textType);
  if (!textarea) return;
  var content = textarea.value.trim();
  if (!content) { alert('内容不能为空'); return; }
  try {
    var result = await API.put('/api/lessons/' + textEditState.lessonId + '/text', {
      content: content,
      text_type: textType
    });
    alert('保存成功！单词索引已重建（共 ' + result.total_words + ' 个单词）');
  } catch (e) {
    alert('保存失败: ' + (e.detail || String(e)));
  }
}


// --- Reorder ---
async function moveUnit(bookId, unitId, direction) {
  var units = mgmtData.units[bookId];
  if (!units) return;
  var idx = units.findIndex(function(u) { return u.id === unitId; });
  if (idx < 0) return;
  var newIdx = idx + direction;
  if (newIdx < 0 || newIdx >= units.length) return;
  var ids = units.map(function(u) { return u.id; });
  var tmp = ids[idx]; ids[idx] = ids[newIdx]; ids[newIdx] = tmp;
  try {
    await API.put('/api/books/' + bookId + '/units/reorder', { ids: ids });
    await loadMgmtUnits(bookId);
  } catch (e) {
    alert('排序失败: ' + (e.detail || String(e)));
  }
}

async function moveLesson(unitId, lessonId, direction) {
  var lessons = mgmtData.lessons[unitId];
  if (!lessons) return;
  var idx = lessons.findIndex(function(l) { return l.id === lessonId; });
  if (idx < 0) return;
  var newIdx = idx + direction;
  if (newIdx < 0 || newIdx >= lessons.length) return;
  var ids = lessons.map(function(l) { return l.id; });
  var tmp = ids[idx]; ids[idx] = ids[newIdx]; ids[newIdx] = tmp;
  try {
    await API.put('/api/units/' + unitId + '/lessons/reorder', { ids: ids });
    await loadMgmtLessons(unitId);
  } catch (e) {
    alert('排序失败: ' + (e.detail || String(e)));
  }
}

function escAttr(str) {
  if (str === undefined || str === null) return '';
  return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// --- Excluded Words ---
async function excludeVocabWord(wordId, word, btn) {
  if (!confirm('\u786e\u5b9a\u8981\u4ece\u751f\u8bcd\u8868\u4e2d\u6392\u9664 \"' + esc(word) + '\" \u5417\uff1f\n\u6392\u9664\u540e\u8be5\u8bcd\u4e0d\u4f1a\u518d\u51fa\u73b0\u5728\u751f\u8bcd\u8868\u548c\u6d4b\u9a8c\u4e2d\u3002')) return;
  try {
    await API.post('/api/words/' + wordId + '/exclude');
    var row = btn.closest('tr');
    if (row) row.remove();
  } catch (e) {
    alert('\u64cd\u4f5c\u5931\u8d25: ' + (e.detail || String(e)));
  }
}

async function loadExcludedWords() {
  try {
    var words = await API.get('/api/excluded');
    renderExcludedTable(words);
  } catch (e) {
    document.getElementById('excluded-result').innerHTML = '<p style="color:var(--danger)">\u52a0\u8f7d\u5931\u8d25</p>';
  }
}

function renderExcludedTable(words) {
  var html = '';
  if (words.length === 0) {
    html = '<p style="color:var(--text-light)">\u6682\u65e0\u6392\u9664\u8bcd</p>';
  } else {
    html += '<p class="vocab-summary">\u5171 ' + words.length + ' \u4e2a\u6392\u9664\u8bcd</p>';
    html += '<table class="vocab-table"><thead><tr><th>\u5355\u8bcd</th><th>\u6dfb\u52a0\u65f6\u95f4</th><th>\u64cd\u4f5c</th></tr></thead><tbody>';
    for (var i = 0; i < words.length; i++) {
      html += '<tr>';
      html += '<td class="word-cell">' + esc(words[i].word) + '</td>';
      html += '<td>' + esc(words[i].created_at || '-') + '</td>';
      html += '<td><button class="btn-sm" onclick="removeExcludedWord(\x27' + escAttr(words[i].word).replace(/'/g, "\\'") + '\x27, this)">\u2705 \u53d6\u6d88\u6392\u9664</button></td>';
      html += '</tr>';
    }
    html += '</tbody></table>';
  }
  document.getElementById('excluded-result').innerHTML = html;
}

async function addExcludedWord() {
  var input = document.getElementById('inp-excluded-word');
  var word = input.value.trim();
  if (!word) { alert('\u8bf7\u8f93\u5165\u8981\u6392\u9664\u7684\u5355\u8bcd'); return; }
  try {
    await API.post('/api/excluded', { word: word });
    input.value = '';
    loadExcludedWords();
  } catch (e) {
    alert('\u6dfb\u52a0\u5931\u8d25: ' + (e.detail || String(e)));
  }
}

async function removeExcludedWord(word, btn) {
  try {
    await API.delete('/api/excluded/' + encodeURIComponent(word));
    var row = btn.closest('tr');
    if (row) row.remove();
    loadExcludedWords();
  } catch (e) {
    alert('\u64cd\u4f5c\u5931\u8d25: ' + (e.detail || String(e)));
  }
}

loadBooks();



// --- Data Migration ---

async function loadExportBooks() {
  try {
    const books = await API.get('/api/books');
    const sel = document.getElementById('sel-export-book');
    sel.innerHTML = '<option value="">-- 选择课本 --</option>';
    books.forEach(b => {
      sel.innerHTML += '<option value="' + escAttr(b.id) + '">' + esc(b.name) + '</option>';
    });
  } catch (e) {
    console.error('Failed to load books for export', e);
  }
}

function _downloadJSON(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function _showMigrateResult(msg, isError) {
  const el = document.getElementById('migrate-result');
  el.style.display = 'block';
  el.style.background = isError ? '#FFEBEE' : '#E8F5E9';
  el.style.border = isError ? '1px solid #EF9A9A' : '1px solid #A5D6A7';
  el.innerHTML = msg;
}

async function exportSelectedBook() {
  const bookId = document.getElementById('sel-export-book').value;
  if (!bookId) { alert('请先选择一本课本'); return; }
  try {
    const resp = await fetch('/api/export/textbook/' + bookId);
    if (!resp.ok) throw new Error('导出失败');
    const data = await resp.json();
    const bookName = data.books[0].name.replace(/\s+/g, '_');
    _downloadJSON(data, 'textbook_export_' + bookName + '.json');
    _showMigrateResult('✅ 已导出课本: ' + esc(data.books[0].name));
  } catch (e) {
    _showMigrateResult('❌ 导出失败: ' + esc(String(e)), true);
  }
}

async function exportAllTextbooks() {
  try {
    const resp = await fetch('/api/export/textbooks');
    if (!resp.ok) throw new Error('导出失败');
    const data = await resp.json();
    _downloadJSON(data, 'textbook_export_all.json');
    _showMigrateResult('✅ 已导出全部 ' + data.books.length + ' 本教材，共 ' + data.excluded_words.length + ' 个排除词');
  } catch (e) {
    _showMigrateResult('❌ 导出失败: ' + esc(String(e)), true);
  }
}

async function exportQuizData() {
  try {
    const resp = await fetch('/api/export/quiz');
    if (!resp.ok) throw new Error('导出失败');
    const data = await resp.json();
    _downloadJSON(data, 'quiz_export.json');
    _showMigrateResult('✅ 已导出 ' + data.logs.length + ' 条测验记录');
  } catch (e) {
    _showMigrateResult('❌ 导出失败: ' + esc(String(e)), true);
  }
}

function _readFile(inputId) {
  return new Promise((resolve, reject) => {
    const input = document.getElementById(inputId);
    if (!input.files || !input.files.length) {
      reject(new Error('请先选择文件'));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      try { resolve(JSON.parse(reader.result)); }
      catch (e) { reject(new Error('JSON 解析失败，请检查文件格式')); }
    };
    reader.onerror = () => reject(new Error('文件读取失败'));
    reader.readAsText(input.files[0]);
  });
}

async function importTextbooks() {
  try {
    const data = await _readFile('file-import-textbook');
    const clear = document.getElementById('chk-import-textbook-clear').checked;
    if (clear && !confirm('确定要清除所有现有教材数据后导入吗？此操作不可恢复！')) return;
    const result = await API.post('/api/import/textbooks', { data, clear });
    _showMigrateResult(
      '✅ 教材导入完成：导入 ' + result.books_imported + ' 本课本，' +
      '创建 ' + result.lessons_created + ' 课，' +
      '新增 ' + result.words_imported + ' 个单词，' +
      '添加 ' + result.excluded_added + ' 个排除词' +
      (result.books_skipped > 0 ? '，跳过 ' + result.books_skipped + ' 本（已存在）' : '')
    );
    loadBooks();
    loadExportBooks();
  } catch (e) {
    _showMigrateResult('❌ 导入失败: ' + esc(e.detail || String(e)), true);
  }
}

async function importQuiz() {
  try {
    const data = await _readFile('file-import-quiz');
    const clear = document.getElementById('chk-import-quiz-clear').checked;
    if (clear && !confirm('确定要清除所有现有测验记录后导入吗？此操作不可恢复！')) return;
    const result = await API.post('/api/import/quiz', { data, clear });
    _showMigrateResult(
      '✅ 测验导入完成：导入 ' + result.imported + ' 条记录' +
      (result.skipped > 0 ? '，跳过 ' + result.skipped + ' 条（单词不存在）' : '')
    );
  } catch (e) {
    _showMigrateResult('❌ 导入失败: ' + esc(e.detail || String(e)), true);
  }
}
