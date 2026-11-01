import React from 'react';
import { Link } from 'react-router';
import { metaApi } from '../api/client';
import { useFetch } from '../hooks/useFetch';

const Footer: React.FC = () => {
  const { data: meta } = useFetch(metaApi.getMeta, []);

  return (
    <footer className="border-t mt-8 py-6">
      <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
        <p className="flex items-baseline justify-center gap-3">
          <span className="font-semibold text-foreground">Home Energy Usage Tracker</span>
          <span>Local deployment • No cloud services</span>
        </p>
        <p className="mt-2">
          <Link to="/backup-restore" className="underline-offset-4 hover:underline">
            Backup/Restore
          </Link>
        </p>
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
