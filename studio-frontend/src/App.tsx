import { useUrlSync } from '@/viewmodels/nav/urlSync';
import { StudioPage } from '@/views/pages/StudioPage';
import { MainLayout } from '@/views/templates/MainLayout';

const App = () => {
    // Bind the URL hash to navigation: back/forward and deep-links both work.
    useUrlSync();
    return (
        <MainLayout>
            <StudioPage />
        </MainLayout>
    );
};

export default App;
