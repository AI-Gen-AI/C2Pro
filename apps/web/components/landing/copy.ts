/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
export type LandingLocale = "es" | "en";

type NavItem = {
  label: string;
  href: string;
};

type LinkedText = {
  text: string;
  href: string;
};

type Bullet = {
  strong: string;
  text: string;
};

type WaitlistFormCopy = {
  fields: {
    name: {
      label: string;
      placeholder: string;
    };
    company: {
      label: string;
      placeholder: string;
    };
    role: {
      label: string;
      placeholder: string;
    };
    email: {
      label: string;
      placeholder: string;
    };
    volume: {
      label: string;
      options: Array<{
        value: "under_20" | "20_100" | "over_100";
        label: string;
      }>;
    };
  };
  consent: {
    beforeLink: string;
    linkLabel: string;
    afterLink: string;
  };
  submit: string;
  success: string;
  error: string;
};

export type LandingCopy = {
  header: {
    nav: NavItem[];
    signIn: string;
    cta: string;
    workspace: string;
    microTag: string;
    localeSwitch: NavItem;
  };
  hero: {
    badge: string;
    h1: string;
    lead: string;
    ctaPrimary: string;
    ctaSecondary: string;
    trustNote: string;
  };
  console: {
    barTitle: string;
    badges: string[];
    rows: Array<{
      name: string;
      status: string;
      tone: "neutral" | "warning" | "risk" | "success";
    }>;
    evidenceKey: string;
    quote: string;
    tags: string[];
    foot: string;
    footBadge: string;
  };
  dimensions: {
    eyebrow: string;
    h2: string;
    prose: string;
    cards: Array<{
      title: string;
      text: string;
    }>;
    chipsLabel: string;
    chips: string[];
  };
  supervision: {
    eyebrow: string;
    h2: string;
    prose: string;
    bullets: Bullet[];
  };
  howItWorks: {
    eyebrow: string;
    h2: string;
    lead: string;
    steps: Array<{
      number: string;
      title: string;
      text: string;
    }>;
  };
  originLimits: {
    eyebrow: string;
    h2: string;
    ecosystem: {
      h3: string;
      textBeforeLink: string;
      link: LinkedText;
      textAfterLink: string;
    };
    limits: {
      h3: string;
      text: string;
    };
  };
  waitlist: {
    eyebrow: string;
    h2: string;
    lead: string;
    checks: string[];
    formTitle: string;
    fallbackPrefix: string;
    fallbackLink: LinkedText;
    form: WaitlistFormCopy;
  };
  footer: {
    tagline: string;
    ecosystem: LinkedText;
    columns: Array<{
      title: string;
      links: NavItem[];
    }>;
    bottom: string;
    legal: NavItem[];
    localeSwitch: NavItem;
  };
};

const aiGenLinks = {
  home: "https://www.ai-gen.ai",
  services: "https://www.ai-gen.ai/services",
  lab: "https://www.ai-gen.ai/lab",
  dossier: "https://www.ai-gen.ai/dossier",
  about: "https://www.ai-gen.ai/about",
  diagnostic: "https://www.ai-gen.ai/services#solicitud",
  legal: "https://www.ai-gen.ai/aviso-legal",
  privacy: "https://www.ai-gen.ai/privacidad",
  cookies: "https://www.ai-gen.ai/cookies",
};

export const landingCopy: Record<LandingLocale, LandingCopy> = {
  es: {
    header: {
      nav: [
        { label: "Producto", href: "#producto" },
        { label: "Cómo funciona", href: "#como-funciona" },
        { label: "Origen", href: "#origen" },
        { label: "Piloto", href: "#waitlist" },
      ],
      signIn: "Iniciar sesión",
      cta: "Unirse al piloto",
      workspace: "Ir al workspace",
      microTag: "un producto AI-Gen",
      localeSwitch: { label: "EN", href: "/en" },
    },
    hero: {
      badge: "Programa piloto · en validación",
      h1: "Tres documentos. Una sola verdad.",
      lead: "C2Pro cruza contrato, cronograma y presupuesto para detectar incoherencias, desviaciones y riesgos — con evidencia citada y validación humana experta antes de cada decisión.",
      ctaPrimary: "Unirse al piloto",
      ctaSecondary: "Ver demo ilustrativa",
      trustNote:
        "Acceso prioritario y condiciones de fundador para las primeras organizaciones piloto.",
    },
    console: {
      barTitle: "C2Pro · Workspace del proyecto",
      badges: ["Vista ilustrativa", "Human approval queue"],
      rows: [
        { name: "Contrato_principal.pdf", status: "Evidence linked", tone: "neutral" },
        { name: "Cronograma_obra.pdf", status: "2 desviaciones", tone: "warning" },
        { name: "Presupuesto_v3.xlsx", status: "Desviación 2,8 %", tone: "risk" },
        { name: "Oferta_proveedor_A.pdf", status: "Sin incidencias", tone: "success" },
      ],
      evidenceKey: "Coherencia · Presupuesto · DET-BUD-SUM",
      quote:
        "«La suma de partidas (636 M) difiere del total declarado (654 M): desviación del 2,8 %.»",
      tags: ["Contrato", "Cronograma", "Presupuesto"],
      foot: "Validación · Especialista en compras",
      footBadge: "Pending approval",
    },
    dimensions: {
      eyebrow: "Auditoría tridimensional",
      h2: "Contrato, cronograma y presupuesto, leídos como un solo sistema.",
      prose:
        "La mayoría de los sobrecostes no viven en un documento: viven entre documentos. C2Pro construye una vista cruzada del proyecto y resume su estado con el Coherence Score™ — un índice 0–100 en el que cada hallazgo queda vinculado a su evidencia.",
      cards: [
        {
          title: "Contrato",
          text: "Cláusulas, penalizaciones, hitos y obligaciones, extraídos y trazados.",
        },
        {
          title: "Cronograma",
          text: "Plazos y dependencias, contrastados con lo que el contrato promete.",
        },
        {
          title: "Presupuesto",
          text: "Partidas y totales, cuadrados contra el precio contractual.",
        },
      ],
      chipsLabel: "Seis dimensiones de análisis",
      chips: ["Alcance", "Presupuesto", "Calidad", "Técnica", "Legal", "Plazos"],
    },
    supervision: {
      eyebrow: "La ventaja de la supervisión humana",
      h2: "Velocidad de máquina, criterio de experto.",
      prose:
        "C2Pro no decide por ti. Procesa el volumen documental y eleva los hallazgos a un especialista que los valida antes de que lleguen a tu mesa. Esa supervisión es lo que convierte un análisis rápido en una decisión defendible.",
      bullets: [
        {
          strong: "Hallazgos vinculados a su fuente.",
          text: " Cada riesgo apunta a documento, página y cláusula.",
        },
        {
          strong: "Revisión humana obligatoria",
          text: " antes de emitir el informe.",
        },
        {
          strong: "Trazabilidad de extremo a extremo,",
          text: " de la carga al informe final.",
        },
      ],
    },
    howItWorks: {
      eyebrow: "Cómo funciona",
      h2: "Un protocolo de control, no una caja negra.",
      lead:
        "Entradas, control humano y salida. No publicamos la lógica interna del análisis.",
      steps: [
        {
          number: "01",
          title: "Cargas la documentación",
          text: "Contrato, cronograma, presupuesto y ofertas.",
        },
        {
          number: "02",
          title: "El sistema analiza",
          text: "Cruza documentos y detecta posibles incoherencias.",
        },
        {
          number: "03",
          title: "Un experto valida",
          text: "Revisión humana y priorización de hallazgos.",
        },
        {
          number: "04",
          title: "Informe accionable",
          text: "Con trazabilidad a la fuente.",
        },
      ],
    },
    originLimits: {
      eyebrow: "Origen y límites",
      h2: "Nace del oficio. Conoce sus límites.",
      ecosystem: {
        h3: "Parte del ecosistema AI-Gen",
        textBeforeLink:
          "C2Pro no es un software buscando problema: nace de años revisando pliegos, contratos y ofertas a mano, y del trabajo de AI-Gen en inteligencia documental aplicada con gobernanza. Conoce el ecosistema en ",
        link: { text: "ai-gen.ai", href: aiGenLinks.home },
        textAfterLink: ".",
      },
      limits: {
        h3: "Qué no hace",
        text: "C2Pro no firma por ti, no sustituye el criterio del comprador y no promete detección perfecta. Señala, evidencia y prioriza; la decisión — y la responsabilidad — siguen siendo humanas. Todo informe pasa revisión experta antes de llegar a tu mesa.",
      },
    },
    waitlist: {
      eyebrow: "Programa piloto en validación",
      h2: "Plazas limitadas para organizaciones con alto volumen documental.",
      lead:
        "Estamos incorporando un número limitado de organizaciones para validar C2Pro en casos reales. Acceso prioritario y condiciones de fundador para los primeros pilotos.",
      checks: [
        "Onboarding acompañado con especialista",
        "Revisión humana experta de cada informe",
        "Condiciones de fundador",
      ],
      formTitle: "Solicitar acceso al piloto",
      fallbackPrefix: "",
      fallbackLink: { text: "info@ai-gen.ai", href: "mailto:info@ai-gen.ai" },
      form: {
        fields: {
          name: { label: "Nombre", placeholder: "Nombre y apellidos" },
          company: { label: "Empresa", placeholder: "Empresa" },
          role: { label: "Cargo", placeholder: "Tu cargo" },
          email: {
            label: "Email corporativo",
            placeholder: "nombre@empresa.com",
          },
          volume: {
            label: "Volumen documental mensual (opcional)",
            options: [
              { value: "under_20", label: "Menos de 20 documentos" },
              { value: "20_100", label: "20–100 documentos" },
              { value: "over_100", label: "Más de 100 documentos" },
            ],
          },
        },
        consent: {
          beforeLink: "Acepto el tratamiento de mis datos conforme a la política de privacidad",
          linkLabel: "RGPD",
          afterLink: ".",
        },
        submit: "Solicitar acceso",
        success: "Gracias. Te contactaremos para coordinar tu acceso al piloto.",
        error:
          "No hemos podido registrar tu solicitud. Inténtalo de nuevo o escríbenos a info@ai-gen.ai.",
      },
    },
    footer: {
      tagline: "Inteligencia documental para compras y contratos",
      ecosystem: {
        text: "Parte del ecosistema AI-Gen · The Intelligence Generation",
        href: aiGenLinks.home,
      },
      columns: [
        {
          title: "Producto",
          links: [
            { label: "Cómo funciona", href: "#como-funciona" },
            { label: "Demo ilustrativa", href: "/demo/coherence-v1" },
            { label: "Piloto", href: "#waitlist" },
            { label: "Iniciar sesión", href: "/login" },
          ],
        },
        {
          title: "AI-Gen",
          links: [
            { label: "Advisory", href: aiGenLinks.services },
            { label: "AI-Gen Lab", href: aiGenLinks.lab },
            { label: "Dossier", href: aiGenLinks.dossier },
            { label: "Nosotros", href: aiGenLinks.about },
          ],
        },
        {
          title: "Contacto",
          links: [
            { label: "info@ai-gen.ai", href: "mailto:info@ai-gen.ai" },
            { label: "Acceso al piloto", href: "#waitlist" },
            { label: "Solicitar diagnóstico", href: aiGenLinks.diagnostic },
          ],
        },
      ],
      bottom: "© 2026 C2Pro · Parte de AI-Gen.ai",
      legal: [
        { label: "Aviso legal", href: aiGenLinks.legal },
        { label: "Privacidad (RGPD)", href: aiGenLinks.privacy },
        { label: "Cookies", href: aiGenLinks.cookies },
      ],
      localeSwitch: { label: "EN", href: "/en" },
    },
  },
  en: {
    header: {
      nav: [
        { label: "Product", href: "#producto" },
        { label: "How it works", href: "#como-funciona" },
        { label: "Origin", href: "#origen" },
        { label: "Pilot", href: "#waitlist" },
      ],
      signIn: "Sign in",
      cta: "Join the pilot",
      workspace: "Go to workspace",
      microTag: "an AI-Gen product",
      localeSwitch: { label: "ES", href: "/" },
    },
    hero: {
      badge: "Pilot program · in validation",
      h1: "Three documents. One single truth.",
      lead:
        "C2Pro cross-checks contract, schedule and budget to surface inconsistencies, deviations and risks — with cited evidence and expert human validation before every decision.",
      ctaPrimary: "Join the pilot",
      ctaSecondary: "View illustrative demo",
      trustNote:
        "Priority access and founder terms for the first pilot organizations.",
    },
    console: {
      barTitle: "C2Pro · Project workspace",
      badges: ["Illustrative view", "Human approval queue"],
      rows: [
        { name: "Master_contract.pdf", status: "Evidence linked", tone: "neutral" },
        { name: "Works_schedule.pdf", status: "2 deviations", tone: "warning" },
        { name: "Budget_v3.xlsx", status: "2.8 % deviation", tone: "risk" },
        { name: "Supplier_offer_A.pdf", status: "No issues", tone: "success" },
      ],
      evidenceKey: "Coherence · Budget · DET-BUD-SUM",
      quote:
        "“The sum of line items (636 M) differs from the declared total (654 M): a 2.8 % deviation.”",
      tags: ["Contract", "Schedule", "Budget"],
      foot: "Validation · Procurement specialist",
      footBadge: "Pending approval",
    },
    dimensions: {
      eyebrow: "Three-dimensional audit",
      h2: "Contract, schedule and budget, read as one system.",
      prose:
        "Most cost overruns don't live in one document: they live between documents. C2Pro builds a cross-document view of your project and summarizes its state with the Coherence Score™ — a 0–100 index where every finding stays linked to its evidence.",
      cards: [
        {
          title: "Contract",
          text: "Clauses, penalties, milestones and obligations — extracted and traced.",
        },
        {
          title: "Schedule",
          text: "Deadlines and dependencies, checked against what the contract promises.",
        },
        {
          title: "Budget",
          text: "Line items and totals, reconciled against the contract price.",
        },
      ],
      chipsLabel: "Six dimensions of analysis",
      chips: ["Scope", "Budget", "Quality", "Technical", "Legal", "Time"],
    },
    supervision: {
      eyebrow: "The human-oversight advantage",
      h2: "Machine speed, expert judgment.",
      prose:
        "C2Pro doesn't decide for you. It processes the document volume and raises findings to a specialist who validates them before they reach your desk. That oversight is what turns a fast analysis into a defensible decision.",
      bullets: [
        {
          strong: "Findings linked to their source.",
          text: " Every risk points to document, page and clause.",
        },
        {
          strong: "Mandatory human review",
          text: " before any report is issued.",
        },
        {
          strong: "End-to-end traceability,",
          text: " from upload to final report.",
        },
      ],
    },
    howItWorks: {
      eyebrow: "How it works",
      h2: "A control protocol, not a black box.",
      lead:
        "Inputs, human control, output. We don't publish the internal analysis logic.",
      steps: [
        {
          number: "01",
          title: "Upload the documentation",
          text: "Contract, schedule, budget and offers.",
        },
        {
          number: "02",
          title: "The system analyzes",
          text: "Cross-checks documents and flags potential inconsistencies.",
        },
        {
          number: "03",
          title: "An expert validates",
          text: "Human review and prioritization of findings.",
        },
        {
          number: "04",
          title: "Actionable report",
          text: "With traceability to the source.",
        },
      ],
    },
    originLimits: {
      eyebrow: "Origin and limits",
      h2: "Born from the trade. Aware of its limits.",
      ecosystem: {
        h3: "Part of the AI-Gen ecosystem",
        textBeforeLink:
          "C2Pro is not software looking for a problem: it was born from years of reviewing tenders, contracts and offers by hand, and from AI-Gen's work in governed, applied document intelligence. Meet the ecosystem at ",
        link: { text: "ai-gen.ai", href: aiGenLinks.home },
        textAfterLink: ".",
      },
      limits: {
        h3: "What it does not do",
        text: "C2Pro doesn't sign for you, doesn't replace the buyer's judgment, and doesn't promise perfect detection. It flags, evidences and prioritizes; the decision — and the responsibility — remain human. Every report passes expert review before reaching your desk.",
      },
    },
    waitlist: {
      eyebrow: "Pilot program in validation",
      h2: "Limited seats for organizations with high document volume.",
      lead:
        "We are onboarding a limited number of organizations to validate C2Pro on real cases. Priority access and founder terms for the first pilots.",
      checks: [
        "Guided onboarding with a specialist",
        "Expert human review of every report",
        "Founder terms",
      ],
      formTitle: "Request pilot access",
      fallbackPrefix: "",
      fallbackLink: { text: "info@ai-gen.ai", href: "mailto:info@ai-gen.ai" },
      form: {
        fields: {
          name: { label: "Name", placeholder: "Full name" },
          company: { label: "Company", placeholder: "Company" },
          role: { label: "Role", placeholder: "Your role" },
          email: { label: "Work email", placeholder: "name@company.com" },
          volume: {
            label: "Monthly document volume (optional)",
            options: [
              { value: "under_20", label: "Fewer than 20 documents" },
              { value: "20_100", label: "20–100 documents" },
              { value: "over_100", label: "More than 100 documents" },
            ],
          },
        },
        consent: {
          beforeLink: "I accept the processing of my data under the privacy policy",
          linkLabel: "GDPR",
          afterLink: ".",
        },
        submit: "Request access",
        success: "Thank you. We'll contact you to coordinate your pilot access.",
        error:
          "We couldn't register your request. Try again or write to info@ai-gen.ai.",
      },
    },
    footer: {
      tagline: "Document intelligence for procurement and contracts",
      ecosystem: {
        text: "Part of the AI-Gen ecosystem · The Intelligence Generation",
        href: aiGenLinks.home,
      },
      columns: [
        {
          title: "Product",
          links: [
            { label: "How it works", href: "#como-funciona" },
            { label: "Illustrative demo", href: "/demo/coherence-v1" },
            { label: "Pilot", href: "#waitlist" },
            { label: "Sign in", href: "/login" },
          ],
        },
        {
          title: "AI-Gen",
          links: [
            { label: "Advisory", href: aiGenLinks.services },
            { label: "AI-Gen Lab", href: aiGenLinks.lab },
            { label: "Dossier", href: aiGenLinks.dossier },
            { label: "Nosotros", href: aiGenLinks.about },
          ],
        },
        {
          title: "Contact",
          links: [
            { label: "info@ai-gen.ai", href: "mailto:info@ai-gen.ai" },
            { label: "Pilot access", href: "#waitlist" },
            { label: "Request a diagnostic", href: aiGenLinks.diagnostic },
          ],
        },
      ],
      bottom: "© 2026 C2Pro · Part of AI-Gen.ai",
      legal: [
        { label: "Legal notice", href: aiGenLinks.legal },
        { label: "Privacy (GDPR)", href: aiGenLinks.privacy },
        { label: "Cookies", href: aiGenLinks.cookies },
      ],
      localeSwitch: { label: "ES", href: "/" },
    },
  },
};
