(() => {
  "use strict";

  document.documentElement.classList.add("js");

  const SELECTORS = {
    header: "[data-site-header], .site-header",
    menuToggle: "[data-menu-toggle]",
    mobileMenu: "[data-mobile-menu]",
    serviceForm: "[data-service-form]",
    formStep: "[data-form-step]",
    reveal: "[data-reveal]",
  };

  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  );

  const onReady = (callback) => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
      return;
    }
    callback();
  };

  const getFocusableElements = (container) =>
    Array.from(
      container.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((element) => {
      const styles = window.getComputedStyle(element);
      return !element.hidden && styles.display !== "none" && styles.visibility !== "hidden";
    });

  const setupHeader = () => {
    const header = document.querySelector(SELECTORS.header);
    if (!header) return;

    let lastScrollY = Math.max(window.scrollY, 0);
    let ticking = false;

    const updateHeader = () => {
      const scrollY = Math.max(window.scrollY, 0);
      const delta = scrollY - lastScrollY;
      const isNearTop = scrollY < 24;
      const isScrollingDown = delta > 6;
      const isScrollingUp = delta < -6;

      header.classList.toggle("is-scrolled", !isNearTop);
      header.classList.toggle("is-compact", scrollY > 80);

      if (isNearTop || isScrollingUp || document.body.classList.contains("menu-open")) {
        header.classList.remove("is-hidden");
        header.classList.add("is-visible");
      } else if (isScrollingDown && scrollY > 180) {
        header.classList.add("is-hidden");
        header.classList.remove("is-visible");
      }

      if (isScrollingDown) header.dataset.scrollDirection = "down";
      if (isScrollingUp) header.dataset.scrollDirection = "up";

      lastScrollY = scrollY;
      ticking = false;
    };

    window.addEventListener(
      "scroll",
      () => {
        if (ticking) return;
        ticking = true;
        window.requestAnimationFrame(updateHeader);
      },
      { passive: true },
    );

    updateHeader();
  };

  const setupMobileMenu = () => {
    const toggle = document.querySelector(SELECTORS.menuToggle);
    const menu = document.querySelector(SELECTORS.mobileMenu);
    if (!toggle || !menu) return;

    if (!menu.id) menu.id = "mobile-navigation";
    toggle.setAttribute("aria-controls", menu.id);
    toggle.setAttribute("aria-expanded", "false");
    menu.hidden = true;
    menu.setAttribute("aria-hidden", "true");
    if (!menu.hasAttribute("tabindex")) menu.setAttribute("tabindex", "-1");

    let isOpen = false;
    let previouslyFocused = null;
    let lockedScrollY = 0;
    let previousBodyStyles = null;

    const lockBody = () => {
      lockedScrollY = window.scrollY;
      previousBodyStyles = {
        position: document.body.style.position,
        top: document.body.style.top,
        width: document.body.style.width,
        overflow: document.body.style.overflow,
      };
      document.body.style.position = "fixed";
      document.body.style.top = `-${lockedScrollY}px`;
      document.body.style.width = "100%";
      document.body.style.overflow = "hidden";
      document.body.classList.add("menu-open");
    };

    const unlockBody = () => {
      if (!previousBodyStyles) return;
      document.body.style.position = previousBodyStyles.position;
      document.body.style.top = previousBodyStyles.top;
      document.body.style.width = previousBodyStyles.width;
      document.body.style.overflow = previousBodyStyles.overflow;
      document.body.classList.remove("menu-open");
      window.scrollTo(0, lockedScrollY);
      previousBodyStyles = null;
    };

    const openMenu = () => {
      if (isOpen) return;
      isOpen = true;
      previouslyFocused = document.activeElement;
      menu.hidden = false;
      menu.setAttribute("aria-hidden", "false");
      menu.classList.add("is-open");
      toggle.classList.add("is-active");
      toggle.setAttribute("aria-expanded", "true");
      toggle.setAttribute(
        "aria-label",
        toggle.dataset.labelClose || "Cerrar menú",
      );
      lockBody();

      window.requestAnimationFrame(() => {
        const firstFocusable = getFocusableElements(menu)[0];
        (firstFocusable || menu).focus({ preventScroll: true });
      });
    };

    const closeMenu = ({ restoreFocus = true } = {}) => {
      if (!isOpen) return;
      isOpen = false;
      menu.hidden = true;
      menu.setAttribute("aria-hidden", "true");
      menu.classList.remove("is-open");
      toggle.classList.remove("is-active");
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute(
        "aria-label",
        toggle.dataset.labelOpen || "Abrir menú",
      );
      unlockBody();

      if (restoreFocus && previouslyFocused instanceof HTMLElement) {
        previouslyFocused.focus({ preventScroll: true });
      }
      previouslyFocused = null;
    };

    toggle.addEventListener("click", () => {
      if (isOpen) closeMenu();
      else openMenu();
    });

    menu.addEventListener("click", (event) => {
      const closeControl = event.target.closest(
        "[data-menu-close], [data-menu-dismiss], a[href]",
      );
      if (!closeControl && event.target !== menu) return;
      const followsLink = closeControl && closeControl.matches("a[href]");
      closeMenu({ restoreFocus: !followsLink });
    });

    document.addEventListener("keydown", (event) => {
      if (!isOpen) return;

      if (event.key === "Escape") {
        event.preventDefault();
        closeMenu();
        return;
      }

      if (event.key !== "Tab") return;
      const focusable = getFocusableElements(menu);
      if (!focusable.length) {
        event.preventDefault();
        menu.focus({ preventScroll: true });
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    const desktopQuery = window.matchMedia("(min-width: 64rem)");
    const closeAtDesktop = (event) => {
      if (event.matches) closeMenu({ restoreFocus: false });
    };
    if (desktopQuery.addEventListener) {
      desktopQuery.addEventListener("change", closeAtDesktop);
    } else {
      desktopQuery.addListener(closeAtDesktop);
    }
  };

  const cleanAttributionValue = (value) =>
    String(value || "")
      .replace(/[\u0000-\u001f\u007f]/g, "")
      .trim()
      .slice(0, 200);

  const getAttribution = () => {
    const keys = [
      "utm_source",
      "utm_medium",
      "utm_campaign",
      "utm_content",
      "utm_term",
    ];
    const params = new URLSearchParams(window.location.search);
    let stored = {};

    try {
      stored = JSON.parse(sessionStorage.getItem("cw_attribution_v1") || "{}");
    } catch (_error) {
      stored = {};
    }
    if (!stored || typeof stored !== "object" || Array.isArray(stored)) stored = {};
    stored = [...keys, "source"].reduce((safeValues, key) => {
      const value = cleanAttributionValue(stored[key]);
      if (value) safeValues[key] = value;
      return safeValues;
    }, {});

    const current = {};
    keys.forEach((key) => {
      const value = cleanAttributionValue(params.get(key));
      if (value) current[key] = value;
    });

    const explicitSource = cleanAttributionValue(
      params.get("source") || params.get("src"),
    );
    let referrerSource = "";
    if (document.referrer) {
      try {
        const referrerHost = new URL(document.referrer).hostname;
        if (referrerHost && referrerHost !== window.location.hostname) {
          referrerSource = cleanAttributionValue(referrerHost);
        }
      } catch (_error) {
        referrerSource = "";
      }
    }

    const hasCurrentCampaign = Object.keys(current).length > 0 || explicitSource;
    const attribution = hasCurrentCampaign
      ? {
          ...current,
          source:
            explicitSource || current.utm_source || referrerSource || "direct",
        }
      : {
          ...stored,
          source: stored.source || referrerSource || "direct",
        };

    try {
      sessionStorage.setItem("cw_attribution_v1", JSON.stringify(attribution));
    } catch (_error) {
      // Storage can be unavailable in strict privacy modes; attribution still works in-page.
    }

    return attribution;
  };

  const addAttributionFields = (form, attribution) => {
    Object.entries(attribution).forEach(([name, value]) => {
      if (!value) return;
      const existing = Array.from(form.elements).find(
        (field) => field.name === name,
      );

      if (existing) {
        if (existing.type === "hidden" && !existing.value) existing.value = value;
        return;
      }

      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      input.dataset.attribution = "true";
      form.append(input);
    });
  };

  const setupServiceForm = (form, formIndex, attribution) => {
    const steps = Array.from(form.querySelectorAll(SELECTORS.formStep));
    if (!steps.length) return;

    addAttributionFields(form, attribution);
    form.noValidate = true;
    form.classList.add("is-enhanced");

    let currentStep = 0;
    let submitting = false;
    let dirty = false;
    let generatedErrorCount = 0;
    const clientErrors = new WeakMap();

    let status = form.querySelector("[data-form-status]");
    if (!status) {
      status = document.createElement("p");
      status.className = "form-status sr-only";
      status.dataset.formStatus = "";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");
      status.setAttribute("aria-atomic", "true");
      form.prepend(status);
    } else if (status.closest(SELECTORS.formStep)) {
      form.insertBefore(status, form.querySelector(SELECTORS.formStep));
    }

    let progressBar = form.querySelector("[data-form-progress]");
    let progressContainer = progressBar
      ? progressBar.closest(".form-progress") || progressBar
      : null;
    if (!progressBar) {
      progressContainer = document.createElement("div");
      progressContainer.className = "form-progress";
      progressContainer.innerHTML =
        '<progress data-form-progress></progress><span data-progress-text></span>';
      status.insertAdjacentElement("afterend", progressContainer);
      progressBar = progressContainer.querySelector("[data-form-progress]");
    }

    const progressFill =
      progressContainer.querySelector("[data-progress-fill]") ||
      (progressBar.matches("progress") ? null : progressBar.firstElementChild);
    const progressText = form.querySelector("[data-progress-text]");
    const progressPercent = form.querySelector("[data-progress-percent]");
    progressContainer.setAttribute("aria-label", "Progreso de la solicitud");

    const ensureStepControls = (step, index) => {
      if (steps.length < 2) return;
      let actions = step.querySelector("[data-step-actions]");

      const getActions = () => {
        if (actions) return actions;
        actions = document.createElement("div");
        actions.className = "form-step-actions";
        actions.dataset.stepActions = "";
        step.append(actions);
        return actions;
      };

      if (index > 0 && !step.querySelector("[data-step-back]")) {
        const back = document.createElement("button");
        back.type = "button";
        back.className = "button button-tertiary";
        back.dataset.stepBack = "";
        back.textContent = "Atrás";
        getActions().prepend(back);
      }

      if (index < steps.length - 1 && !step.querySelector("[data-step-next]")) {
        const next = document.createElement("button");
        next.type = "button";
        next.className = "button button-primary";
        next.dataset.stepNext = "";
        next.textContent = "Continuar";
        getActions().append(next);
      }
    };

    const stepControls = (step) =>
      Array.from(step.querySelectorAll("input, select, textarea")).filter(
        (field) => field.willValidate && !field.disabled,
      );

    const validationGroup = (field) => {
      if (field.type !== "radio" || !field.name) return [field];
      return Array.from(form.elements).filter(
        (candidate) =>
          candidate instanceof HTMLInputElement &&
          candidate.type === "radio" &&
          candidate.name === field.name,
      );
    };

    const errorMessage = (field) => {
      const validity = field.validity;
      if (validity.valueMissing) {
        if (field.type === "checkbox") {
          return field.name === "privacy_accepted"
            ? "Debes aceptar el tratamiento indicado para enviar la solicitud."
            : "Marca esta casilla para continuar.";
        }
        if (field.type === "radio" || field.tagName === "SELECT") {
          return "Selecciona una opción para continuar.";
        }
        return "Completa este campo para continuar.";
      }
      if (validity.typeMismatch && field.type === "email") {
        return "Ingresa un correo electrónico válido.";
      }
      if (validity.tooShort) {
        return `Usa al menos ${field.minLength} caracteres.`;
      }
      if (validity.tooLong) {
        return `Usa como máximo ${field.maxLength} caracteres.`;
      }
      if (validity.patternMismatch) return "Revisa el formato de este campo.";
      if (validity.rangeUnderflow) return `El valor mínimo es ${field.min}.`;
      if (validity.rangeOverflow) return `El valor máximo es ${field.max}.`;
      return field.validationMessage || "Revisa este campo.";
    };

    const addDescription = (field, id) => {
      const ids = new Set((field.getAttribute("aria-describedby") || "").split(/\s+/));
      ids.delete("");
      ids.add(id);
      field.setAttribute("aria-describedby", Array.from(ids).join(" "));
    };

    const removeDescription = (field, id) => {
      const ids = (field.getAttribute("aria-describedby") || "")
        .split(/\s+/)
        .filter((item) => item && item !== id);
      if (ids.length) field.setAttribute("aria-describedby", ids.join(" "));
      else field.removeAttribute("aria-describedby");
    };

    const showFieldError = (field) => {
      const group = validationGroup(field);
      const anchor = group[0];
      let error = clientErrors.get(anchor);

      if (!error) {
        generatedErrorCount += 1;
        error = document.createElement("p");
        error.id = `form-${formIndex}-error-${generatedErrorCount}`;
        error.className = "field-errors field-errors-client";
        error.dataset.clientError = "";
        const host =
          anchor.closest("[data-field], .form-field, .field, .form-group, fieldset") ||
          anchor.parentElement;
        host.append(error);
        clientErrors.set(anchor, error);
      }

      error.textContent = errorMessage(field);
      group.forEach((control) => {
        control.dataset.clientInvalid = "true";
        control.setAttribute("aria-invalid", "true");
        addDescription(control, error.id);
      });
    };

    const clearFieldError = (field) => {
      const group = validationGroup(field);
      const anchor = group[0];
      const error = clientErrors.get(anchor);
      if (error) {
        group.forEach((control) => {
          removeDescription(control, error.id);
          if (control.dataset.clientInvalid === "true") {
            control.removeAttribute("aria-invalid");
            delete control.dataset.clientInvalid;
          }
        });
        error.remove();
        clientErrors.delete(anchor);
      } else {
        group.forEach((control) => {
          if (control.dataset.clientInvalid === "true") {
            control.removeAttribute("aria-invalid");
            delete control.dataset.clientInvalid;
          }
        });
      }
    };

    const syncContactPreferenceValidity = () => {
      const preferenceFields = Array.from(form.elements).filter(
        (field) => field.name === "contact_preference",
      );
      const selectedPreference = preferenceFields.find(
        (field) => field.checked || field.tagName === "SELECT",
      );
      const preference = selectedPreference ? selectedPreference.value : "";
      const whatsapp = Array.from(form.elements).find(
        (field) => field.name === "whatsapp",
      );
      const email = Array.from(form.elements).find(
        (field) => field.name === "email",
      );

      [whatsapp, email].forEach((field) => {
        if (!field || field.dataset.contactConditional !== "true") return;
        field.setCustomValidity("");
        delete field.dataset.contactConditional;
        if (field.checkValidity()) clearFieldError(field);
      });

      if (preference === "whatsapp" && whatsapp && !whatsapp.value.trim()) {
        whatsapp.setCustomValidity(
          "Ingresa un número de WhatsApp para usar este canal.",
        );
        whatsapp.dataset.contactConditional = "true";
      }
      if (preference === "email" && email && !email.value.trim()) {
        email.setCustomValidity(
          "Ingresa un correo electrónico para usar este canal.",
        );
        email.dataset.contactConditional = "true";
      }
    };

    const validateStep = (index, { announce = true, focus = true } = {}) => {
      syncContactPreferenceValidity();
      const controls = stepControls(steps[index]);
      const checkedRadioGroups = new Set();
      const invalid = [];

      controls.forEach((field) => {
        if (field.type === "radio" && field.name) {
          if (checkedRadioGroups.has(field.name)) return;
          checkedRadioGroups.add(field.name);
        }

        if (field.checkValidity()) clearFieldError(field);
        else {
          showFieldError(field);
          invalid.push(field);
        }
      });

      if (!invalid.length) return { valid: true, firstInvalid: null };

      if (announce) {
        status.textContent = `Revisa ${invalid.length === 1 ? "el campo indicado" : "los campos indicados"} antes de continuar.`;
      }

      if (focus) {
        window.requestAnimationFrame(() => {
          invalid[0].focus({ preventScroll: true });
          invalid[0].scrollIntoView({
            behavior: prefersReducedMotion.matches ? "auto" : "smooth",
            block: "center",
          });
          invalid[0].reportValidity();
        });
      }

      return { valid: false, firstInvalid: invalid[0] };
    };

    const updateProgress = () => {
      const humanStep = currentStep + 1;
      const percent = Math.round((humanStep / steps.length) * 100);

      progressContainer.style.setProperty("--form-progress", `${percent}%`);
      if (progressBar) {
        if (progressBar.matches("progress")) {
          progressBar.setAttribute("max", String(steps.length));
          progressBar.setAttribute("value", String(humanStep));
        } else {
          progressBar.setAttribute("aria-valuemin", "1");
          progressBar.setAttribute("aria-valuemax", String(steps.length));
          progressBar.setAttribute("aria-valuenow", String(humanStep));
        }
        progressBar.setAttribute("aria-valuetext", `Paso ${humanStep} de ${steps.length}`);
      }
      if (progressFill) progressFill.style.width = `${percent}%`;
      if (progressText) progressText.textContent = `Paso ${humanStep} de ${steps.length}`;
      if (progressPercent) progressPercent.textContent = `${percent}%`;

      form.querySelectorAll("[data-step-indicator]").forEach((indicator, index) => {
        indicator.classList.toggle("is-active", index === currentStep);
        indicator.classList.toggle("is-complete", index < currentStep);
        if (index === currentStep) indicator.setAttribute("aria-current", "step");
        else indicator.removeAttribute("aria-current");
      });
    };

    const showStep = (index, { moveFocus = true } = {}) => {
      currentStep = Math.min(Math.max(index, 0), steps.length - 1);
      steps.forEach((step, stepIndex) => {
        const active = stepIndex === currentStep;
        step.hidden = !active;
        step.classList.toggle("is-active", active);
        step.setAttribute("aria-hidden", String(!active));
      });
      updateProgress();

      if (!moveFocus) return;
      const heading = steps[currentStep].querySelector("h2, h3, legend, [data-step-title]");
      const focusTarget = heading || stepControls(steps[currentStep])[0];
      if (focusTarget) {
        const hadTabindex = focusTarget.hasAttribute("tabindex");
        if (!hadTabindex) focusTarget.setAttribute("tabindex", "-1");
        focusTarget.focus({ preventScroll: true });
        focusTarget.scrollIntoView({
          behavior: prefersReducedMotion.matches ? "auto" : "smooth",
          block: "start",
        });
        if (!hadTabindex) {
          focusTarget.addEventListener(
            "blur",
            () => focusTarget.removeAttribute("tabindex"),
            { once: true },
          );
        }
      }
      status.textContent = `Paso ${currentStep + 1} de ${steps.length}.`;
    };

    steps.forEach((step, index) => {
      if (!step.id) step.id = `service-form-${formIndex}-step-${index + 1}`;
      ensureStepControls(step, index);
    });

    const serverErrorIndex = steps.findIndex((step) =>
      step.querySelector(
        ".errorlist:not(:empty), [data-server-error], .field-error:not([data-client-error]), .has-error, [aria-invalid=\"true\"]",
      ),
    );
    showStep(serverErrorIndex >= 0 ? serverErrorIndex : 0, { moveFocus: false });
    if (serverErrorIndex >= 0) {
      status.textContent = "Revisa los errores indicados en este paso.";
    }

    form.addEventListener("click", (event) => {
      const next = event.target.closest("[data-step-next]");
      if (next && form.contains(next)) {
        event.preventDefault();
        const result = validateStep(currentStep);
        if (result.valid) showStep(currentStep + 1);
        return;
      }

      const back = event.target.closest("[data-step-back]");
      if (back && form.contains(back)) {
        event.preventDefault();
        showStep(currentStep - 1);
      }
    });

    form.addEventListener("keydown", (event) => {
      const target = event.target;
      if (
        event.key !== "Enter" ||
        currentStep >= steps.length - 1 ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLButtonElement ||
        target.type === "file"
      ) {
        return;
      }

      event.preventDefault();
      const result = validateStep(currentStep);
      if (result.valid) showStep(currentStep + 1);
    });

    form.addEventListener("input", (event) => {
      const field = event.target;
      if (!(field instanceof HTMLInputElement || field instanceof HTMLSelectElement || field instanceof HTMLTextAreaElement)) {
        return;
      }
      if (field.type !== "hidden" && !field.dataset.attribution) dirty = true;
      if (["contact_preference", "whatsapp", "email"].includes(field.name)) {
        syncContactPreferenceValidity();
      }
      if (field.checkValidity()) clearFieldError(field);
    });

    form.addEventListener("change", (event) => {
      const field = event.target;
      if (!(field instanceof HTMLInputElement || field instanceof HTMLSelectElement || field instanceof HTMLTextAreaElement)) {
        return;
      }
      if (field.type !== "hidden" && !field.dataset.attribution) dirty = true;
      if (["contact_preference", "whatsapp", "email"].includes(field.name)) {
        syncContactPreferenceValidity();
      }
      if (field.checkValidity()) clearFieldError(field);
    });

    const mediaInput = Array.from(form.elements).find(
      (field) => field.name === "diagnostic_media" && field.type === "file",
    );
    if (mediaInput) {
      const allowedTypes = new Set([
        "image/jpeg",
        "image/pjpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "application/mp4",
      ]);
      const allowedExtensions = new Set(["jpg", "jpeg", "png", "webp", "mp4"]);
      if (!mediaInput.accept) {
        mediaInput.accept = ".jpg,.jpeg,.png,.webp,.mp4,image/jpeg,image/png,image/webp,video/mp4";
      }

      const maxBytesAttribute = Number(mediaInput.dataset.maxBytes || 0);
      const maxImageBytes = Number(
        mediaInput.dataset.maxImageBytes || maxBytesAttribute || 0,
      );
      const maxVideoBytes = Number(
        mediaInput.dataset.maxVideoBytes || maxBytesAttribute || 0,
      );
      const maxMegabytesAttribute = Number(
        mediaInput.dataset.maxSizeMb || mediaInput.dataset.maxMb || 0,
      );
      const maxBytes =
        maxBytesAttribute > 0
          ? maxBytesAttribute
          : maxMegabytesAttribute > 0
            ? maxMegabytesAttribute * 1024 * 1024
            : 0;

      let mediaRules =
        form.querySelector("[data-media-rules]") ||
        mediaInput.closest("[data-field-wrap]")?.querySelector(".field-help");
      if (!mediaRules) {
        mediaRules = document.createElement("p");
        mediaRules.id = `form-${formIndex}-media-rules`;
        mediaRules.className = "form-help";
        mediaRules.dataset.mediaRules = "";
        mediaInput.insertAdjacentElement("afterend", mediaRules);
      } else if (!mediaRules.id) {
        mediaRules.id = `form-${formIndex}-media-rules`;
      }
      if (!mediaRules.textContent.trim()) {
        const formatMegabytes = (bytes) =>
          (bytes / (1024 * 1024)).toFixed(1).replace(".0", "");
        const limits =
          maxImageBytes && maxVideoBytes && maxImageBytes !== maxVideoBytes
            ? `. Imágenes hasta ${formatMegabytes(maxImageBytes)} MB; MP4 hasta ${formatMegabytes(maxVideoBytes)} MB`
            : maxBytes
              ? `. Tamaño máximo: ${formatMegabytes(maxBytes)} MB`
              : "";
        mediaRules.textContent = `Formatos permitidos: JPEG, PNG, WEBP y MP4${limits}.`;
      }
      addDescription(mediaInput, mediaRules.id);

      let preview = form.querySelector("[data-media-preview]");
      if (!preview) {
        preview = document.createElement("div");
        preview.className = "media-preview";
        preview.dataset.mediaPreview = "";
        preview.hidden = true;
        mediaRules.insertAdjacentElement("afterend", preview);
      }

      let objectUrl = "";
      const clearPreview = ({ clearInput = false } = {}) => {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = "";
        const image = preview.querySelector("[data-media-image]");
        const video = preview.querySelector("[data-media-video]");
        const name = preview.querySelector("[data-media-name]");
        const size = preview.querySelector("[data-media-size]");
        const icon = preview.querySelector("[data-media-file-icon]");
        if (image) {
          image.removeAttribute("src");
          image.hidden = true;
        }
        if (video) {
          video.pause();
          video.removeAttribute("src");
          video.load();
          video.hidden = true;
        }
        if (name) name.textContent = "";
        if (size) size.textContent = "";
        if (icon) icon.hidden = true;
        preview.hidden = true;
        if (clearInput) mediaInput.value = "";
      };

      const validateMedia = (file) => {
        mediaInput.setCustomValidity("");
        if (!file) return true;
        const extension = file.name.includes(".")
          ? file.name.split(".").pop().toLowerCase()
          : "";
        const supported =
          allowedExtensions.has(extension) &&
          (!file.type || allowedTypes.has(file.type));
        if (!supported) {
          mediaInput.setCustomValidity(
            "Adjunta un archivo JPEG, PNG, WEBP o MP4 válido.",
          );
          return false;
        }
        const applicableMaximum = extension === "mp4" ? maxVideoBytes : maxImageBytes;
        const effectiveMaximum = applicableMaximum || maxBytes;
        if (effectiveMaximum && file.size > effectiveMaximum) {
          mediaInput.setCustomValidity(
            `El archivo supera el límite de ${(effectiveMaximum / (1024 * 1024)).toFixed(1).replace(".0", "")} MB.`,
          );
          return false;
        }
        return true;
      };

      const renderPreview = (file) => {
        clearPreview();
        objectUrl = URL.createObjectURL(file);
        const isVideo = file.name.toLowerCase().endsWith(".mp4");
        let image = preview.querySelector("[data-media-image]");
        let video = preview.querySelector("[data-media-video]");
        let name = preview.querySelector("[data-media-name]");
        let size = preview.querySelector("[data-media-size]");

        if (!image || !video || !name || !size) {
          preview.innerHTML =
            '<img data-media-image hidden><video controls preload="metadata" data-media-video hidden></video><p><strong data-media-name></strong> · <span data-media-size></span></p><div class="media-preview-actions"><button type="button" class="text-button" data-media-replace>Cambiar archivo</button><button type="button" class="text-button" data-media-remove>Quitar archivo</button></div>';
          image = preview.querySelector("[data-media-image]");
          video = preview.querySelector("[data-media-video]");
          name = preview.querySelector("[data-media-name]");
          size = preview.querySelector("[data-media-size]");
        }

        image.hidden = isVideo;
        video.hidden = !isVideo;
        if (isVideo) {
          video.src = objectUrl;
          video.setAttribute("aria-label", `Vista previa de ${file.name}`);
        } else {
          image.src = objectUrl;
          image.alt = `Vista previa de ${file.name}`;
        }
        name.textContent = file.name;
        size.textContent = `${(file.size / (1024 * 1024)).toFixed(1)} MB`;
        preview.hidden = false;
      };

      mediaInput.addEventListener("change", () => {
        const file = mediaInput.files && mediaInput.files[0];
        clearPreview();
        if (!file) {
          mediaInput.setCustomValidity("");
          clearFieldError(mediaInput);
          return;
        }
        if (!validateMedia(file)) {
          showFieldError(mediaInput);
          status.textContent = "El archivo adjunto no cumple los requisitos indicados.";
          return;
        }
        clearFieldError(mediaInput);
        renderPreview(file);
      });

      form.addEventListener("click", (event) => {
        const remove = event.target.closest("[data-media-remove]");
        if (remove && form.contains(remove)) {
          event.preventDefault();
          clearPreview({ clearInput: true });
          mediaInput.setCustomValidity("");
          clearFieldError(mediaInput);
          mediaInput.focus();
          status.textContent = "Archivo adjunto eliminado.";
          return;
        }

        const replace = event.target.closest("[data-media-replace]");
        if (replace && form.contains(replace)) {
          event.preventDefault();
          mediaInput.click();
        }
      });

      window.addEventListener(
        "pagehide",
        () => {
          if (objectUrl) URL.revokeObjectURL(objectUrl);
        },
        { once: true },
      );
    }

    form.addEventListener("submit", (event) => {
      if (submitting) {
        event.preventDefault();
        return;
      }

      let firstInvalidStep = -1;
      let firstInvalidField = null;
      steps.forEach((_step, index) => {
        const result = validateStep(index, { announce: false, focus: false });
        if (!result.valid && firstInvalidStep < 0) {
          firstInvalidStep = index;
          firstInvalidField = result.firstInvalid;
        }
      });

      if (firstInvalidStep >= 0) {
        event.preventDefault();
        showStep(firstInvalidStep, { moveFocus: false });
        status.textContent = "Revisa los campos indicados antes de enviar la solicitud.";
        window.requestAnimationFrame(() => {
          firstInvalidField.focus({ preventScroll: true });
          firstInvalidField.scrollIntoView({
            behavior: prefersReducedMotion.matches ? "auto" : "smooth",
            block: "center",
          });
          firstInvalidField.reportValidity();
        });
        return;
      }

      submitting = true;
      dirty = false;
      form.classList.add("is-submitting");
      form.setAttribute("aria-busy", "true");
      status.textContent = "Enviando tu solicitud…";

      const submitButtons = form.querySelectorAll(
        'button[type="submit"], input[type="submit"]',
      );
      submitButtons.forEach((button) => {
        button.setAttribute("aria-disabled", "true");
        if (button instanceof HTMLButtonElement) {
          const label = button.querySelector("[data-submit-label]");
          if (label) label.textContent = "Enviando…";
          else button.textContent = "Enviando…";
        } else {
          button.value = "Enviando…";
        }
      });

      window.requestAnimationFrame(() => {
        submitButtons.forEach((button) => {
          button.disabled = true;
        });
      });
    });

    window.addEventListener("beforeunload", (event) => {
      if (!dirty || submitting) return;
      event.preventDefault();
      event.returnValue = "";
    });
  };

  const setupScrollReveal = () => {
    const elements = Array.from(document.querySelectorAll(SELECTORS.reveal));
    if (!elements.length) return;

    if (prefersReducedMotion.matches || !("IntersectionObserver" in window)) {
      elements.forEach((element) => element.classList.add("is-visible"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -8%", threshold: 0.12 },
    );

    elements.forEach((element) => observer.observe(element));
  };

  const setupMobileKeyboard = () => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const mobile = window.matchMedia("(max-width: 699px)");
    let frame = 0;
    const update = () => {
      frame = 0;
      const focused = document.activeElement;
      const isEditing = focused && (
        focused.matches("input:not([type=hidden]), textarea, select") ||
        focused.isContentEditable
      );
      document.body.classList.toggle(
        "is-keyboard-open",
        Boolean(mobile.matches && isEditing && viewport.height < window.innerHeight - 150),
      );
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    viewport.addEventListener("resize", schedule);
    document.addEventListener("focusin", schedule);
    document.addEventListener("focusout", schedule);
    mobile.addEventListener("change", schedule);
  };

  const setupWhatsappOrb = () => {
    const orb = document.querySelector("[data-whatsapp-orb]");
    const link = orb && orb.querySelector("[data-whatsapp-orb-link]");
    if (!link || prefersReducedMotion.matches) return;
    const readFlag = (key) => {
      try { return sessionStorage.getItem(key) === "1"; }
      catch (_error) { return true; }
    };
    const saveFlag = (key) => {
      try { sessionStorage.setItem(key, "1"); }
      catch (_error) { /* Sin almacenamiento, no insistimos en otras vistas. */ }
    };
    if (!readFlag("cw_whatsapp_intro_v1")) {
      saveFlag("cw_whatsapp_intro_v1");
      orb.classList.add("is-intro");
      window.setTimeout(() => orb.classList.remove("is-intro"), 700);
    }
    if (!readFlag("cw_whatsapp_label_v1")) {
      saveFlag("cw_whatsapp_label_v1");
      window.setTimeout(() => {
        if (document.hidden || document.body.classList.contains("menu-open") ||
            window.matchMedia("(max-width: 699px)").matches) return;
        orb.classList.add("is-label-visible");
        window.setTimeout(() => orb.classList.remove("is-label-visible"), 4200);
      }, 3000);
    }
    link.addEventListener("click", () => orb.classList.remove("is-label-visible"));
  };

  const setupSmartVideos = () => {
    const videos = Array.from(document.querySelectorAll("[data-smart-video]"));
    if (!videos.length) return;

    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    const saveData = Boolean(connection && connection.saveData);
    const slowConnection = Boolean(connection && /^(slow-2g|2g)$/.test(connection.effectiveType || ""));
    const allowAutoplay = !prefersReducedMotion.matches && !saveData && !slowConnection;
    let activeVideo = null;
    let pendingVideo = null;
    const visibility = new Map();

    const loadVideo = (video) => {
      if (video.dataset.videoLoaded === "true") return;
      const source = video.dataset.videoSrc;
      if (!source) return;
      video.src = source;
      video.dataset.videoLoaded = "true";
      video.load();
    };

    const updateControls = (video) => {
      const container = video.closest("[data-video-preview]");
      const playButton = container && container.querySelector("[data-video-play]");
      const audioButton = container && container.querySelector("[data-video-audio]");
      if (playButton) {
        const isPlaying = !video.paused && !video.ended;
        const videoLabel = video.hasAttribute("data-manual-only") ? "video completo" : "vista previa";
        playButton.textContent = isPlaying ? "Pausar" : "Reproducir";
        playButton.setAttribute("aria-label", `${isPlaying ? "Pausar" : "Reproducir"} ${videoLabel}`);
      }
      if (audioButton) {
        audioButton.hidden = video.paused;
        audioButton.textContent = video.muted ? "Activar sonido" : "Silenciar";
        audioButton.setAttribute("aria-label", video.muted ? "Activar sonido" : "Silenciar");
      }
    };

    const pauseVideo = (video) => {
      if (!video.paused) video.pause();
      if (activeVideo === video) activeVideo = null;
      if (pendingVideo === video) pendingVideo = null;
      updateControls(video);
    };

    const playVideo = async (video, { manual = false } = {}) => {
      if (document.hidden || (!manual && (!allowAutoplay || video.hasAttribute("data-manual-only")))) return;
      if (pendingVideo === video) return;
      if (activeVideo && activeVideo !== video) pauseVideo(activeVideo);
      if (pendingVideo && pendingVideo !== video) pauseVideo(pendingVideo);
      pendingVideo = video;
      loadVideo(video);
      if (!manual) video.muted = true;
      try {
        await video.play();
        if (pendingVideo !== video) {
          video.pause();
          return;
        }
        activeVideo = video;
      } catch (_error) {
        // Poster y botón de reproducción siguen disponibles si el navegador bloquea autoplay.
      } finally {
        if (pendingVideo === video) pendingVideo = null;
      }
      updateControls(video);
    };

    const chooseVisibleVideo = () => {
      const mostVisible = [...visibility.entries()]
        .filter(([video, ratio]) => ratio >= 0.65 && !video.hasAttribute("data-manual-only"))
        .sort((a, b) => b[1] - a[1])[0];
      if (!mostVisible || !allowAutoplay || document.hidden) {
        if (activeVideo && visibility.get(activeVideo) < 0.65) pauseVideo(activeVideo);
        return;
      }
      if (activeVideo !== mostVisible[0]) playVideo(mostVisible[0]);
    };

    videos.forEach((video) => {
      visibility.set(video, 0);
      video.muted = true;
      video.addEventListener("play", () => updateControls(video));
      video.addEventListener("pause", () => updateControls(video));
      const container = video.closest("[data-video-preview]");
      const playButton = container && container.querySelector("[data-video-play]");
      const audioButton = container && container.querySelector("[data-video-audio]");
      if (playButton) {
        playButton.addEventListener("click", () => {
          if (!video.paused) pauseVideo(video);
          else playVideo(video, { manual: true });
        });
      }
      if (audioButton) {
        audioButton.addEventListener("click", () => {
          video.muted = !video.muted;
          updateControls(video);
        });
      }
      updateControls(video);
    });

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          visibility.set(entry.target, entry.intersectionRatio);
          if (entry.intersectionRatio < 0.65 && activeVideo === entry.target) {
            pauseVideo(entry.target);
          }
        });
        chooseVisibleVideo();
      }, { threshold: [0, 0.25, 0.65, 0.85, 1] });
      videos.forEach((video) => observer.observe(video));
    }

    document.addEventListener("visibilitychange", () => {
      if (document.hidden && activeVideo) pauseVideo(activeVideo);
      else chooseVisibleVideo();
    });
    window.addEventListener("pagehide", () => {
      if (activeVideo) pauseVideo(activeVideo);
    });
  };

  onReady(() => {
    setupHeader();
    setupMobileMenu();
    setupMobileKeyboard();
    setupWhatsappOrb();
    const attribution = getAttribution();
    document.querySelectorAll(SELECTORS.serviceForm).forEach((form, index) => {
      setupServiceForm(form, index + 1, attribution);
    });
    document.querySelectorAll("a[data-whatsapp-message]").forEach((link) => {
      try {
        const url = new URL(link.href);
        if (url.hostname !== "wa.me") return;
        url.searchParams.set("text", link.dataset.whatsappMessage || "");
        link.href = url.toString();
      } catch (_error) {
        // El enlace directo a WhatsApp sigue funcionando si la URL no es válida.
      }
    });
    setupSmartVideos();
    setupScrollReveal();
  });
})();
