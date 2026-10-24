/* DOM observation and actionability for Snow Ball.
 * Pipeline follows Nanobrowser's observe -> revalidate -> dispatch-once design.
 * This small DOM adapter is specific to Snow Ball; upstream samples are in research/.
 */
(() => {
  const selector = 'button,a[href],input,select,textarea,[contenteditable]:not([contenteditable="false"]),[role="button"],[role="link"],[role="tab"],[role="menuitem"],[role="combobox"],[role="checkbox"],[role="radio"],[onclick]';
  const clean = (value, max = 80) => String(value || '').replace(/\s+/g, ' ').trim().slice(0, max);
  function safeText(el) {
    if (!el || el.isContentEditable || el.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),script,style')) return '';
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let value = '', node;
    while ((node = walker.nextNode()) && value.length < 700) {
      if (!node.parentElement?.isContentEditable && !node.parentElement?.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),script,style')) value += ' ' + node.textContent;
    }
    return clean(value, 600);
  }
  function visible(el) {
    if (!el?.isConnected || el.closest('[hidden],[inert],[aria-hidden="true"]') ||
        el.disabled || el.getAttribute('aria-disabled') === 'true') return false;
    const rect = el.getBoundingClientRect(), style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility === 'visible' && style.display !== 'none' && style.opacity !== '0';
  }
  function name(el) {
    const root = el.getRootNode();
    const labelled = (el.getAttribute('aria-labelledby') || '').split(/\s+/)
      .map(id => safeText(root.getElementById?.(id))).filter(Boolean).join(' ');
    return clean(labelled || el.getAttribute('aria-label') ||
      [...(el.labels || [])].map(safeText).join(' ') ||
      (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || el.isContentEditable ? '' : safeText(el)) ||
      el.querySelector('svg title')?.textContent || el.querySelector('img')?.alt ||
      el.getAttribute('title') || el.getAttribute('placeholder'));
  }
  function role(el) {
    return clean(el.getAttribute('role') || ({BUTTON:'button', A:'link', INPUT:'textbox',
      TEXTAREA:'textbox', SELECT:'combobox'})[el.tagName] || el.tagName.toLowerCase(), 32);
  }
  function context(el) {
    const container = el.closest('fieldset,[role="dialog"],dialog,article,[role="row"],li,form,section');
    const heading = container?.querySelector('legend,h1,h2,h3,[role="heading"]');
    return clean([container?.getAttribute('aria-label'), safeText(heading)].filter(Boolean).join(' — '), 120);
  }
  function describe(el) {
    return {label: name(el), role: role(el), context: context(el)};
  }
  function proof(el) { return JSON.stringify(describe(el)); }
  function collect(root = document) {
    const found = [...root.querySelectorAll(selector)];
    for (const el of root.querySelectorAll('*')) if (el.shadowRoot) found.push(...collect(el.shadowRoot));
    return found;
  }
  function canClick(el) {
    if (!visible(el)) return false;
    const description = [name(el), el.tagName === 'INPUT' ? el.type : '', context(el)].join(' ');
    // These controls are always completed by the person.
    if (/password|passcode|otp|one.time|cvv|cvc|aadhaar|aadhar|\bpin\b|pay\b|payment|purchase|delete|remove account|send\b|publish|\bsubmit\b|\bconfirm\b|confirm booking|captcha/i.test(description)) return false;
    if (el.matches('textarea,select,[contenteditable]:not([contenteditable="false"])')) return false;
    if (el.tagName === 'INPUT' && !['button','checkbox','radio'].includes(el.type)) return false;
    if (el.matches('input[type="submit"],button[type="submit"]') || (el.tagName === 'BUTTON' && el.form && !el.hasAttribute('type'))) return false;
    return el.matches('button,a[href],[role="button"],[role="link"],[role="tab"],[role="menuitem"],[role="checkbox"],[role="radio"],input[type="button"],input[type="checkbox"],input[type="radio"]');
  }
  async function click(el, expectedProof, cancelled = () => false) {
    if (cancelled() || !canClick(el) || proof(el) !== expectedProof) throw new Error('The button changed or needs your own click. Please review it.');
    el.scrollIntoView({block:'nearest', inline:'nearest', behavior:'instant'});
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    if (cancelled() || !canClick(el) || proof(el) !== expectedProof) throw new Error('The page changed. Ask Snow Ball to look again.');
    const rect = el.getBoundingClientRect();
    const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
    const hit = document.elementFromPoint(x, y);
    const shadowHit = hit?.shadowRoot?.elementFromPoint(x, y);
    if (!(hit === el || el.contains(hit) || shadowHit === el || el.contains(shadowHit))) throw new Error('Something covers the button. Close it, then try again.');
    el.click(); // One dispatch; no automatic retries or typing.
  }
  window.SnowBallControls = {selector, clean, safeText, visible, name, role, context, describe, proof, collect, canClick, click};
})();


