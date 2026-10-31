import type { ReactElement, ReactNode } from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';

// The app's only global provider (beyond React.StrictMode in main.tsx) is the
// router itself — there is no QueryClientProvider or custom context provider.
// This helper replaces BrowserRouter with a MemoryRouter so tests can drive
// the route they want and still resolve things like useParams/useNavigate.
interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  // The path the element should be mounted at (used to provide route params).
  path?: string;
  // MemoryRouter history entries.
  initialEntries?: string[];
}

export function renderWithProviders(
  ui: ReactElement,
  {
    path = '/',
    initialEntries = [path],
    ...renderOptions
  }: RenderWithProvidersOptions = {},
) {
  function Wrapper({ children }: { children?: ReactNode }) {
    return (
      <MemoryRouter
        initialEntries={initialEntries}
       
      >
        <Routes>
          <Route path={path} element={children} />
        </Routes>
      </MemoryRouter>
    );
  }
  return render(ui, { wrapper: Wrapper, ...renderOptions });
}