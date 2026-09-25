import React from "react";
import { createBrowserRouter } from "react-router";

import { App } from "../App.jsx";

// One route renders the whole shell for now. App still owns the workflow state
// that decides what each screen shows, so it reads the location through
// `routes/paths.js` rather than through nested route elements. As saved
// sessions, drafts, and threads gain their own URLs, they become nested routes
// here with read-only loaders.
export const router = createBrowserRouter([{ path: "*", element: <App /> }]);
