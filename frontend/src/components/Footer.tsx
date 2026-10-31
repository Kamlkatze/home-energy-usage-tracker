import React from 'react';
import { metaApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';

const Footer: React.FC = () => {
  const { data: meta } = useFetch(metaApi.getMeta, []);

  return (
    <footer className="border-t mt-8 py-6">
      <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
        <p>Home Energy Usage Tracker • Local deployment • No cloud services</p>
        <p className="mt-2">Data stays on your machine</p>
        {meta && (
          <p className="mt-2 font-mono text-xs">
            v{meta.app_version} • Commit {meta.git_commit}
          </p>
        )}
      </div>
    </footer>
  );
};

export default Footer;
