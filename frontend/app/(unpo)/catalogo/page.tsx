import Navbar from '../../../components/Navbar';
import ProductCatalog from '../../../components/unpo/ProductCatalog';
import Footer from '../../../components/Footer';

export default function CatalogPage() {
    return (
        <main className="min-h-screen bg-white">
            <Navbar />
            <div className="pt-24">
                <ProductCatalog />
            </div>
            <Footer />
        </main>
    );
}
