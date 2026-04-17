import React from 'react';

const colorMap = {
  financial: 'var(--color-header-financial)',
  strategic: 'var(--color-header-strategic)',
  market: 'var(--color-header-market)',
  decision: 'var(--color-header-decision)',
  results: 'var(--color-header-results)',
  neutral: 'var(--color-header-neutral)',
};

function PanelCard({ title, headerColor = 'neutral', children, actions, className = '', style }) {
  return (
    <div className={`panel-card ${className}`} style={style}>
      {title && (
        <div className="panel-header" style={{ background: colorMap[headerColor] || colorMap.neutral }}>
          <span className="section-header">{title}</span>
          {actions && <div className="panel-actions">{actions}</div>}
        </div>
      )}
      <div className="panel-body">
        {children}
      </div>
    </div>
  );
}

export default PanelCard;
