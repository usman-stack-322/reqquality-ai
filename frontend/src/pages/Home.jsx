import React from 'react';

const FEATURES = [
  {
    icon: 'analysis',
    title: 'Hybrid Requirement Analysis',
    description: 'Rules + Gemini identify ambiguity, missing information, testability issues and assumptions.',
  },
  {
    icon: 'risk',
    title: 'Quality Risk Assessment',
    description: 'Automatically calculate requirement risk and suggested priority.',
  },
  {
    icon: 'tests',
    title: 'Test Scenario Generation',
    description: 'Generate positive, negative, boundary and edge-case test scenarios.',
  },
  {
    icon: 'traceability',
    title: 'Traceability & SQA Review',
    description: 'Track requirements through acceptance criteria, testing and reviewer approval.',
  },
];

const WORKFLOW = [
  'Requirement Input',
  'Hybrid Analysis',
  'Risk & Priority',
  'Acceptance Criteria',
  'Test Scenarios',
  'SQA Review',
];

function FeatureIcon({ name }) {
  const shared = {
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  };

  const shapes = {
    analysis: <><path d="M5 6.5h14M5 12h9M5 17.5h7" /><circle cx="18" cy="16.5" r="3.5" /><path d="m20.5 19 2 2" /></>,
    risk: <><path d="M12 3.5 21 20H3L12 3.5Z" /><path d="M12 9v5M12 17.2h.01" /></>,
    tests: <><path d="M8 4.5h8M9 4.5v6l-4 7.2A2 2 0 0 0 6.8 21h10.4a2 2 0 0 0 1.8-3.3L15 10.5v-6" /><path d="M7.2 16h9.6M10 13h4" /></>,
    traceability: <><path d="M8.5 8.5 6.8 6.8a3.5 3.5 0 0 0-5 5l3 3a3.5 3.5 0 0 0 5 0l1.7-1.7M15.5 15.5l1.7 1.7a3.5 3.5 0 0 0 5-5l-3-3a3.5 3.5 0 0 0-5 0l-1.7 1.7M8 12h8" /></>,
  };

  return <svg aria-hidden="true" viewBox="0 0 24 24" {...shared}>{shapes[name]}</svg>;
}

function WorkflowIllustration() {
  return (
    <svg className="hero-illustration" viewBox="0 0 640 460" role="img" aria-labelledby="workflow-art-title workflow-art-description">
      <title id="workflow-art-title">Requirement quality workflow</title>
      <desc id="workflow-art-description">A requirement moves through AI analysis, quality risk, acceptance criteria, test scenarios and SQA review.</desc>
      <rect x="1" y="1" width="638" height="458" rx="14" fill="#173F35" />
      <path d="M20 54H620" stroke="#42695B" strokeWidth="1" />
      <circle cx="28" cy="28" r="4" fill="#B9CDBD" />
      <text x="42" y="32" fill="#F4EFE6" fontSize="11" fontWeight="700" letterSpacing="1.4">QUALITY WORKFLOW</text>
      <rect x="502" y="17" width="111" height="23" rx="8" fill="#285B4A" />
      <circle cx="515" cy="28.5" r="3" fill="#A9C9AC" />
      <text x="525" y="32" fill="#E8F0E8" fontSize="9" fontWeight="600">PIPELINE ACTIVE</text>

      <path d="M196 143h26m166 0h26M472 198v37m0 0H376m0 0h-91m-91 0h-36m127 0v34m91-34v34m91-34v34" fill="none" stroke="#8FB39B" strokeWidth="2" />
      <path d="m216 139 7 4-7 4m166-8 7 4-7 4m-49 84-4 7-4-7m-83 0-4 7-4-7m-83 0-4 7-4-7m278-4-4 7-4-7" fill="none" stroke="#B9D9BB" strokeWidth="1.5" />

      <rect x="24" y="82" width="172" height="116" rx="10" fill="#FBF7F0" />
      <rect x="40" y="99" width="27" height="27" rx="8" fill="#E8E2D6" />
      <path d="M47 106h13M47 112h10M47 118h8" stroke="#285B4A" strokeWidth="1.5" strokeLinecap="round" />
      <text x="76" y="109" fill="#6B706C" fontSize="9" fontWeight="700" letterSpacing=".8">REQUIREMENT</text>
      <text x="40" y="148" fill="#161A18" fontSize="12" fontWeight="700">Clear, testable need</text>
      <path d="M40 162h129M40 172h105" stroke="#D8CEC0" strokeWidth="3" strokeLinecap="round" />
      <rect x="40" y="182" width="52" height="6" rx="3" fill="#AFC6B3" />

      <rect x="222" y="82" width="166" height="116" rx="10" fill="#285B4A" stroke="#6E927E" />
      <rect x="238" y="99" width="27" height="27" rx="8" fill="#3F765F" />
      <path d="M245 106h13M245 112h9M245 118h12" stroke="#F4EFE6" strokeWidth="1.5" strokeLinecap="round" />
      <text x="274" y="109" fill="#D3E1D5" fontSize="9" fontWeight="700" letterSpacing=".8">AI ANALYSIS</text>
      <text x="238" y="148" fill="#FBF7F0" fontSize="12" fontWeight="700">Rules + Gemini</text>
      <text x="238" y="166" fill="#D3E1D5" fontSize="10">Ambiguity · gaps · tests</text>
      <rect x="238" y="181" width="87" height="5" rx="2.5" fill="#8BAF95" />
      <rect x="329" y="181" width="42" height="5" rx="2.5" fill="#466F5A" />

      <rect x="414" y="82" width="202" height="116" rx="10" fill="#FBF7F0" />
      <text x="432" y="109" fill="#6B706C" fontSize="9" fontWeight="700" letterSpacing=".8">QUALITY RISK</text>
      <text x="432" y="154" fill="#161A18" fontSize="31" fontWeight="700">24</text>
      <text x="480" y="153" fill="#6B706C" fontSize="11">/ 100</text>
      <rect x="550" y="126" width="49" height="22" rx="8" fill="#E5EFE4" />
      <text x="563" y="141" fill="#285B4A" fontSize="9" fontWeight="700">LOW</text>
      <path d="M432 169h165" stroke="#E2DACD" strokeWidth="4" strokeLinecap="round" />
      <path d="M432 169h42" stroke="#3F765F" strokeWidth="4" strokeLinecap="round" />
      <text x="432" y="187" fill="#6B706C" fontSize="9">Suggested priority: Medium</text>

      <text x="40" y="264" fill="#B9D9BB" fontSize="9" fontWeight="700" letterSpacing="1">QUALITY VERIFICATION</text>
      <rect x="24" y="283" width="178" height="111" rx="10" fill="#FBF7F0" />
      <circle cx="47" cy="309" r="11" fill="#E8E2D6" />
      <text x="44" y="313" fill="#285B4A" fontSize="10" fontWeight="700">1</text>
      <text x="66" y="312" fill="#6B706C" fontSize="9" fontWeight="700" letterSpacing=".5">ACCEPTANCE</text>
      <text x="40" y="343" fill="#161A18" fontSize="12" fontWeight="700">Criteria</text>
      <path d="M40 359h136M40 370h104M40 381h122" stroke="#D8CEC0" strokeWidth="3" strokeLinecap="round" />

      <rect x="231" y="283" width="178" height="111" rx="10" fill="#FBF7F0" />
      <circle cx="254" cy="309" r="11" fill="#E8E2D6" />
      <text x="251" y="313" fill="#285B4A" fontSize="10" fontWeight="700">2</text>
      <text x="273" y="312" fill="#6B706C" fontSize="9" fontWeight="700" letterSpacing=".5">TEST SCENARIOS</text>
      <text x="247" y="343" fill="#161A18" fontSize="12" fontWeight="700">Positive · boundary</text>
      <text x="247" y="360" fill="#6B706C" fontSize="10">Negative · edge cases</text>
      <rect x="247" y="374" width="58" height="6" rx="3" fill="#AFC6B3" />
      <rect x="311" y="374" width="42" height="6" rx="3" fill="#D8CEC0" />
      <rect x="359" y="374" width="34" height="6" rx="3" fill="#D8CEC0" />

      <rect x="438" y="283" width="178" height="111" rx="10" fill="#285B4A" stroke="#6E927E" />
      <circle cx="461" cy="309" r="11" fill="#3F765F" />
      <path d="m456 309 3 3 7-7" fill="none" stroke="#FBF7F0" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <text x="480" y="312" fill="#D3E1D5" fontSize="9" fontWeight="700" letterSpacing=".5">SQA REVIEW</text>
      <text x="454" y="343" fill="#FBF7F0" fontSize="12" fontWeight="700">Reviewed &amp; approved</text>
      <path d="M454 360h135" stroke="#6E927E" strokeWidth="3" strokeLinecap="round" />
      <rect x="454" y="374" width="69" height="7" rx="3.5" fill="#A9C9AC" />
      <text x="530" y="380" fill="#D3E1D5" fontSize="8">TRACEABLE</text>

      <text x="24" y="431" fill="#B9CDBD" fontSize="9">REQUIREMENT</text>
      <text x="531" y="431" fill="#B9CDBD" fontSize="9">QUALITY READY</text>
    </svg>
  );
}

export default function Home({ user }) {
  const isAnalyst = user?.role === 'Analyst';

  return (
    <div className="landing-page">
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="hero-copy">
          <p className="hero-kicker"><span aria-hidden="true" />AI-Powered Requirements &amp; Software Quality Engineering</p>
          <h1 id="landing-title">Turn unclear requirements into testable, quality-ready specifications.</h1>
          <p className="hero-description">
            ReqQuality AI helps software teams analyze requirements, identify ambiguity and missing information, assess quality risk, generate acceptance criteria and test scenarios, and maintain requirement traceability through SQA review.
          </p>
          <div className="hero-actions">
            {isAnalyst ? (
              <a className="button hero-primary" href="#requirements">Analyze a Requirement<span aria-hidden="true">&rarr;</span></a>
            ) : (
              <a className="button hero-primary" href="#dashboard">Review Requirements<span aria-hidden="true">&rarr;</span></a>
            )}
            <a className="button hero-secondary" href={isAnalyst ? '#dashboard' : '#workflow'}>
              {isAnalyst ? 'View Dashboard' : 'Explore Workflow'}
            </a>
          </div>
          <div className="hero-proof" aria-label="Connected quality workflow">
            <span>Requirements</span><span aria-hidden="true">/</span><span>Testing</span><span aria-hidden="true">/</span><span>SQA review</span>
          </div>
        </div>
        <div className="hero-visual">
          <WorkflowIllustration />
          <p className="visual-caption"><span aria-hidden="true" />A connected path from stakeholder need to verified quality</p>
        </div>
      </section>

      <section className="landing-features" aria-labelledby="features-title">
        <div className="landing-section-heading">
          <p className="landing-eyebrow">ONE CONNECTED WORKSPACE</p>
          <h2 id="features-title">From requirement to quality verification</h2>
          <p>Make each quality decision visible, actionable and traceable.</p>
        </div>
        <div className="feature-grid">
          {FEATURES.map((feature, index) => (
            <article className="feature-card" key={feature.title}>
              <div className="feature-card-top"><span className="feature-icon"><FeatureIcon name={feature.icon} /></span><span className="feature-index">0{index + 1}</span></div>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-workflow" id="workflow" aria-labelledby="workflow-title">
        <div className="landing-section-heading workflow-heading">
          <div><p className="landing-eyebrow">A CLEAR REVIEW PATH</p><h2 id="workflow-title">One workflow. Clear accountability.</h2></div>
          <p>Every stage stays connected to the requirement it verifies.</p>
        </div>
        <ol className="workflow-steps">
          {WORKFLOW.map((step, index) => (
            <li key={step}>
              <span className="workflow-number">0{index + 1}</span>
              <span className="workflow-step-label">{step}</span>
              {index < WORKFLOW.length - 1 && <span className="workflow-arrow" aria-hidden="true">&rarr;</span>}
            </li>
          ))}
        </ol>
      </section>

      <section className="landing-roles" aria-labelledby="roles-title">
        <div className="roles-intro">
          <p className="landing-eyebrow">BUILT FOR COLLABORATION</p>
          <h2 id="roles-title">Clear roles. Shared quality.</h2>
          <p>Analysts and reviewers work from the same requirement record, with each decision carried forward.</p>
        </div>
        <article className="role-panel">
          <span className="role-panel-label">01 / AUTHOR</span>
          <h3>Analyst</h3>
          <ul>
            <li><span aria-hidden="true">&#10003;</span>Creates requirements</li>
            <li><span aria-hidden="true">&#10003;</span>Runs analysis</li>
            <li><span aria-hidden="true">&#10003;</span>Saves and tracks requirements</li>
          </ul>
        </article>
        <article className="role-panel role-panel-reviewer">
          <span className="role-panel-label">02 / VERIFY</span>
          <h3>SQA Reviewer</h3>
          <ul>
            <li><span aria-hidden="true">&#10003;</span>Reviews analyzed requirements</li>
            <li><span aria-hidden="true">&#10003;</span>Verifies quality findings</li>
            <li><span aria-hidden="true">&#10003;</span>Adds reviewer notes</li>
            <li><span aria-hidden="true">&#10003;</span>Approves or requests revision</li>
          </ul>
        </article>
      </section>
    </div>
  );
}
