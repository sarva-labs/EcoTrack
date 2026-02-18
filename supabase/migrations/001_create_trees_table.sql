-- Create trees table
CREATE TABLE IF NOT EXISTS public.trees (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    species VARCHAR(255) NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    estimated_age INTEGER,
    root_spread DECIMAL(10, 2),
    soil_type VARCHAR(100),
    height DECIMAL(10, 2),
    canopy_diameter DECIMAL(10, 2),
    metadata JSONB DEFAULT '{}'::jsonb,
    user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on latitude and longitude for spatial queries
CREATE INDEX IF NOT EXISTS idx_trees_location ON public.trees(latitude, longitude);

-- Create index on species
CREATE INDEX IF NOT EXISTS idx_trees_species ON public.trees(species);

-- Create index on user_id
CREATE INDEX IF NOT EXISTS idx_trees_user_id ON public.trees(user_id);

-- Enable Row Level Security
ALTER TABLE public.trees ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read all trees
CREATE POLICY "Trees are viewable by everyone"
    ON public.trees
    FOR SELECT
    USING (true);

-- Policy: Authenticated users can insert trees
CREATE POLICY "Authenticated users can insert trees"
    ON public.trees
    FOR INSERT
    WITH CHECK (auth.role() = 'authenticated');

-- Policy: Users can update their own trees
CREATE POLICY "Users can update their own trees"
    ON public.trees
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Policy: Users can delete their own trees
CREATE POLICY "Users can delete their own trees"
    ON public.trees
    FOR DELETE
    USING (auth.uid() = user_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updated_at
CREATE TRIGGER update_trees_updated_at
    BEFORE UPDATE ON public.trees
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
