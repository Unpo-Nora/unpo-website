import Navbar from '../../../components/nora/Navbar';
import Hero from '../../../components/nora/Hero';
import ProductShowcase from '../../../components/nora/ProductShowcase';
import WaitlistForm from '../../../components/nora/WaitlistForm';

export default function NoraHome() {
    return (
        <main className="min-h-screen bg-slate-50">
            <Navbar />
            <Hero />
            <ProductShowcase />
            <WaitlistForm />
            {/* Future sections: Featured Products, Story, etc. */}
        </main>
    );
}
