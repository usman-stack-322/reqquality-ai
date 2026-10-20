import React from 'react';

export default function QualityMetrics({ data }) {
  if (!data) return null;
  return <section className="detail-section integrated-metrics" aria-label="Version-aware quality metrics"><h2>Current-version review and test evidence</h2>
    <div className="metric-grid">{[
      ['With linked current test cases',data.requirements_with_linked_cases],
      ['Without linked current test cases',data.requirements_without_linked_cases],
      ['Requirements needing review',data.items_needing_review_count],
    ].map(([label,value])=><article className="metric-card" key={label}><p>{label}</p><strong>{value}</strong></article>)}</div>
    <h3>SQA review statuses</h3><ul>{Object.entries(data.review_status_counts).map(([key,value])=><li key={key}>{key}: {value}</li>)}</ul>
    <h3>Latest Manual execution per current case revision</h3><ul>{Object.entries(data.latest_execution_counts).map(([key,value])=><li key={key}>{key}: {value}</li>)}</ul>
    <h3>Open bugs by severity</h3><ul>{Object.entries(data.open_bugs_by_severity).map(([key,value])=><li key={key}>{key}: {value}</li>)}</ul>
    <details><summary>Metric definitions</summary>{Object.entries(data.metric_definitions).map(([key,value])=><p key={key}>{value}</p>)}</details>
    <h3>Items needing review</h3>{data.items_needing_review.length?<ul>{data.items_needing_review.map(r=><li key={r.id}><a href={`#requirement/${r.id}`}>REQ-{r.id}: {r.title}</a> - version {r.content_revision}: {r.reasons.join('; ')}</li>)}</ul>:<p>No requirements currently flagged for review.</p>}
    {data.items_needing_review_count>data.items_needing_review.length&&<p>Showing the first {data.items_needing_review.length} flagged requirements. Use the requirement register for all records.</p>}
  </section>;
}
