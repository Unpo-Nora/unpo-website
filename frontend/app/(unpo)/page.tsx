import Navbar from '../../components/Navbar';
import Hero from '../../components/Hero';
import Features from '../../components/Features';
import Footer from '../../components/Footer';
import NoraCrossLink from '../../components/NoraCrossLink';
import ContactForm from '../../components/unpo/ContactForm';

export default function Home() {
    return (
        <main className="min-h-screen bg-white">
            <Navbar />
            <Hero />
            <Features />
            <ContactForm />
            <NoraCrossLink />
            <Footer />
        </main>
    );
}
