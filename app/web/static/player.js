/* Custom HTML5 player controller.
 *
 * Receives a `languages` map of { lang: { quality: { src, ... } } } and offers
 * independent language and quality switching. Switching either axis preserves
 * the current playback position and play/pause state (seamless same-timestamp):
 * we capture currentTime + paused, swap the <video> src, then restore on
 * loadedmetadata.
 */
(function () {
  "use strict";

  const root = document.getElementById("tsplayer");
  if (!root) return;

  const data = window.__PLAYER_DATA__;
  const video = document.getElementById("video");
  const langSel = document.getElementById("langSel");
  const qualSel = document.getElementById("qualSel");

  let currentLang = data.lang_list[0];
  let currentQual = (data.quality_by_lang[currentLang] || [])[0];

  function sourcesFor(lang) {
    return data.languages[lang] || {};
  }

  function pickQuality(lang, preferred) {
    const qualities = data.quality_by_lang[lang] || [];
    if (preferred && qualities.indexOf(preferred) !== -1) return preferred;
    return qualities[0];
  }

  function populateQualities(lang) {
    qualSel.innerHTML = "";
    (data.quality_by_lang[lang] || []).forEach(function (q) {
      const opt = document.createElement("option");
      opt.value = q;
      opt.textContent = q;
      qualSel.appendChild(opt);
    });
  }

  function populateLanguages() {
    data.lang_list.forEach(function (l) {
      const opt = document.createElement("option");
      opt.value = l;
      opt.textContent = l;
      langSel.appendChild(opt);
    });
  }

  function load(seamless) {
    const entry = sourcesFor(currentLang)[currentQual];
    if (!entry) return;

    const time = seamless ? video.currentTime : 0;
    const wasPlaying = seamless ? !video.paused : true;

    const restore = function () {
      if (time > 0) {
        try { video.currentTime = time; } catch (e) {}
      }
      if (wasPlaying) {
        const p = video.play();
        if (p && p.catch) p.catch(function () {});
      }
      video.removeEventListener("loadedmetadata", restore);
    };

    video.addEventListener("loadedmetadata", restore);
    video.src = entry.src;
    video.load();
  }

  langSel.addEventListener("change", function () {
    currentLang = langSel.value;
    // Keep the same quality if available under the new language.
    currentQual = pickQuality(currentLang, currentQual);
    populateQualities(currentLang);
    qualSel.value = currentQual;
    load(true); // seamless: language change keeps timestamp + quality intent
  });

  qualSel.addEventListener("change", function () {
    currentQual = qualSel.value; // quality change keeps language
    load(true); // seamless: same timestamp, same language
  });

  // Init
  populateLanguages();
  langSel.value = currentLang;
  populateQualities(currentLang);
  qualSel.value = currentQual;
  load(false);
})();
