import { Injectable, Inject, NotFoundException } from '@nestjs/common';
import { SupabaseClient } from '@supabase/supabase-js';
import { SUPABASE_CLIENT } from '../supabase/supabase.module';
import { CreateTreeDto } from './dto/create-tree.dto';

@Injectable()
export class TreesService {
  constructor(
    @Inject(SUPABASE_CLIENT)
    private readonly supabase: SupabaseClient,
  ) {}

  async create(createTreeDto: CreateTreeDto) {
    const { data, error } = await this.supabase
      .from('trees')
      .insert([createTreeDto])
      .select()
      .single();

    if (error) {
      throw new Error(`Failed to create tree: ${error.message}`);
    }

    return data;
  }

  async findAll(limit = 100, offset = 0) {
    const { data, error } = await this.supabase
      .from('trees')
      .select('*')
      .range(offset, offset + limit - 1);

    if (error) {
      throw new Error(`Failed to fetch trees: ${error.message}`);
    }

    return data;
  }

  async findOne(id: string) {
    const { data, error } = await this.supabase
      .from('trees')
      .select('*')
      .eq('id', id)
      .single();

    if (error) {
      throw new NotFoundException(`Tree with ID ${id} not found`);
    }

    return data;
  }
}
