// --- API helpers ---
const API = {
  get: url => fetch(url).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e))),
  post: (url, data) => fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  }).then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e)))
};

// --- Tab switching ---
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(s => s.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "browse") loadBrowseTree();
  });
});

// --- Input tab ---
let currentBooks = [];

async function loadBooks() {
  currentBooks = await API.get("/api/books");
  const sel = document.getElementById("sel-book");
  sel.innerHTML = "<option value=\"\">-- 请选择或新建 --</option>";
  currentBooks.forEach(b => {
    sel.innerHTML += "<option value=\"" + b.id + "\">" + b.name + "</option>";
  });
}

document.getElementById("sel-book").addEventListener("change", async function() {
  const bookId = parseInt(this.value);
  if (!bookId) { clearUnits(); clearLessons(); return; }
  const units = await API.get("/api/books/" + bookId + "/units");
  const sel = document.getElementById("sel-unit");
  sel.innerHTML = "<option value=\"\">-- 请选择或新建 --</option>";
  units.forEach(u => {
    var label = u.title ? ("单元 " + u.unit_no + " " + u.title) : ("单元 " + u.unit_no);
    sel.innerHTML += "<option value=\"" + u.id + "\">" + label + "</option>";
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
    var label = l.title ? ("课 " + l.lesson_no + " " + l.title) : ("课 " + l.lesson_no);
    sel.innerHTML += "<option value=\"" + l.id + "\">" + label + "</option>";
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
      html += "<p><strong>新单词 (" + result.new_words.length + "):</strong></p><p>";
      result.new_words.forEach(w => {
        const forms = result.word_forms[w] || [w];
        html += "<span class=\"new-word-tag\">" + esc(w) + ": " + esc(forms.join(", ")) + "</span> ";
      });
      html += "</p>";
    } else {
      html += "<p>未发现新单词（所有词都已学过）。</p>";
    }
    div.innerHTML = html;
    document.getElementById("inp-content").value = "";
  } catch (e) {
    alert("错误: " + (e.detail || JSON.stringify(e)));
  }
});

// --- Lookup tab ---
var lookupTimer = null;
document.getElementById("inp-word").addEventListener("input", function() {
  clearTimeout(lookupTimer);
  const word = this.value.trim();
  if (!word) { document.getElementById("lookup-result").style.display = "none"; return; }
  lookupTimer = setTimeout(function() { lookupWord(word); }, 300);
});

async function lookupWord(word) {
  const div = document.getElementById("lookup-result");
  try {
    const r = await API.get("/api/words/" + encodeURIComponent(word));
    div.style.display = "block";
    var html = "<div class=\"word-header\">" + esc(r.word) + "</div>";
    html += "<div class=\"word-path\">首次学习: " + esc(r.first_lesson_path || "未知") + "</div>";
    html += "<div><span class=\"word-stat\">" + r.total_lessons + " 节课</span> <span class=\"word-stat\">" + r.total_count + " 次</span></div>";
    if (r.forms && r.forms.length > 0) {
      html += "<div class=\"word-forms\"><strong>出现形式:</strong> ";
      r.forms.forEach(function(pair) {
        html += "<span class=\"form-tag\">" + esc(pair[0]) + " (" + pair[1] + ")</span>";
      });
      html += "</div>";
    }
    if (r.lessons && r.lessons.length > 0) {
      html += "<ul class=\"lesson-list\">";
      r.lessons.forEach(l => {
        html += "<li>" + esc(l.path) + " <span class=\"id-badge\">(" + l.count + "x)</span></li>";
      });
      html += "</ul>";
    }
    div.innerHTML = html;
  } catch (e) {
    div.style.display = "block";
    div.innerHTML = "<p style=\"color:var(--text-light)\">未找到该单词。</p>";
  }
}

// --- Browse tab ---
async function loadBrowseTree() {
  const container = document.getElementById("browse-tree");
  const books = await API.get("/api/books");
  if (books.length === 0) {
    container.innerHTML = "<p style=\"color:var(--text-light)\">还没有教材，请先录入课文！</p>";
    return;
  }
  var html = "";
  for (var bi = 0; bi < books.length; bi++) {
    const book = books[bi];
    html += "<div class=\"tree-book\">";
    html += "<div class=\"tree-book-title\" onclick=\"toggleNext(this)\">\uD83D\uDCDA " + esc(book.name) + "</div>";
    const units = await API.get("/api/books/" + book.id + "/units");
    for (var ui = 0; ui < units.length; ui++) {
      const unit = units[ui];
      var uLabel = unit.title ? ("单元 " + unit.unit_no + " " + unit.title) : ("单元 " + unit.unit_no);
      html += "<div class=\"tree-unit\" style=\"display:none\">";
      html += "<div class=\"tree-unit-title\" onclick=\"toggleNext(this)\">\uD83D\uDCD6 " + esc(uLabel) + "</div>";
      const lessons = await API.get("/api/units/" + unit.id + "/lessons");
      html += "<div style=\"display:none\">";
      for (var li = 0; li < lessons.length; li++) {
        const lesson = lessons[li];
        var lLabel = lesson.title ? ('课 ' + lesson.lesson_no + ' ' + lesson.title) : ('课 ' + lesson.lesson_no);
        html += '<div class=\"tree-lesson\">';
        html += '<div class=\"tree-lesson-info\" onclick=\"toggleLessonDetail(' + lesson.id + ')\">' + esc(lLabel) + ' <span class=\"id-badge\">[ID:' + lesson.id + ']</span></div>';
        html += '<div class=\"tree-lesson-detail\" id=\"lesson-detail-' + lesson.id + '\">加载中...</div>';
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
        html += '<span class=\"new-word-tag\">' + esc(w) + ': ' + esc(forms.join(', ')) + '</span> ';
      });
    }
    if (wordData.review_words && wordData.review_words.length > 0) {
      html += '<strong>复习单词 (' + wordData.review_words.length + '):</strong> ' + esc(wordData.review_words.join(', '));
    }
    detail.innerHTML = html;
  } catch (e) {
    detail.innerHTML = '<span style=\"color:var(--danger)\">加载失败</span>';
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
      html += '<div class=\"import-entry\">' + esc(e.book_name) + ' U' + e.unit_no + ' L' + e.lesson_no + ' - ' + e.new_word_count + ' 个新词</div>';
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
    div.innerHTML = '<p style=\"color:var(--primary)\">重建完成！共处理 ' + result.total_words + ' 个词元。</p>';
  } catch (e) { alert('错误: ' + (e.detail || JSON.stringify(e))); }
});

function esc(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

loadBooks();
