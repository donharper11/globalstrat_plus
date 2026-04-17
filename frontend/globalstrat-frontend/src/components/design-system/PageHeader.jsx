import React from 'react';
import StatusBadge from './StatusBadge';

function PageHeader({ title, subtitle, status, actions }) {
  return (
    <div className="ds-page-header">
      <div className="ds-page-header-top">
        <div>
          <h1 className="ds-page-title">{title}</h1>
          {(subtitle || status) && (
            <div className="ds-page-header-subtitle">
              {subtitle}
              {status && <StatusBadge status={status} />}
            </div>
          )}
        </div>
        {actions && <div className="panel-actions">{actions}</div>}
      </div>
    </div>
  );
}

export default PageHeader;
